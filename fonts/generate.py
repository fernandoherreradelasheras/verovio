import base64
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as Et
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from typing import Optional

from svgpathtools import Path as SvgPath  # type: ignore

SVG_NS: dict = {"svg": "http://www.w3.org/2000/svg"}

SMUFL_HEADER = """/////////////////////////////////////////////////////////////////////////////
// Name:        smufl.h
// Author:      Laurent Pugin
// Created:     2014-2022
// Copyright (c) Authors and others. All rights reserved.
/////////////////////////////////////////////////////////////////////////////

/////////////////////////////////////////////////////////////////////////////
// NOTE: this file was generated by the ./fonts/generate.py smufl script
// and should not be edited because changes will be lost.
/////////////////////////////////////////////////////////////////////////////

#ifndef __VRV_SMUFL_H__
#define __VRV_SMUFL_H__

//----------------------------------------------------------------------------

namespace vrv {{

//----------------------------------------------------------------------------
// SMUFL glyphs available by default in Verovio
//----------------------------------------------------------------------------

enum {{
{smufl_glyph_list}
}};

/** The number of glyphs for verification **/
#define SMUFL_COUNT {len_smufl_codes}

}} // namespace vrv

#endif
"""

FONTFORGE_SCRIPT = (
    """import os; fontforge.open("{input_fontpath}").generate("{output_fontpath}")"""
)

FONTFACE_WRAPPER = """@font-face {{
    font-family: '{fontname}';
    src: url(data:application/font-woff2;charset=utf-8;base64,{b64encoding}) format('woff2');
    font-weight: normal;
    font-style: normal;
}}"""


B64_FONT_LICENSE = """
This font is licensed under the SIL Open Font License, http://scripts.sil.org/OFL, with 
Reserved Font Name "{fontname}".

See https://github.com/rism-digital/verovio/blob/develop/fonts/README.md for more information.

This file is a subset of the full font containing only the glyphs supported by Verovio for efficiency. 
Please do not use directly.
"""

log = logging.getLogger(__name__)


def generate_smufl(opts: Namespace) -> bool:
    """
    Generates the `smufl.h` file for Verovio.

    :param opts: A set of options from the argument parser sub-command.
    :return: True if successful, False otherwise.
    """
    supported_pth: Path = Path(opts.supported)
    header_out_pth: Path = Path(opts.header_out)
    header_file_pth: Path = Path(header_out_pth, "smufl.h")

    if not supported_pth.is_file() or not os.access(supported_pth, os.R_OK):
        log.error("Could not find or read %s file.", supported_pth)
        return False

    if not os.access(header_out_pth, os.W_OK):
        log.error("Could not write to %s.", header_out_pth)
        return False

    log.debug("SMuFL header will be stored in %s", header_out_pth)
    supported_glyphs: dict = __get_supported_glyph_codes(supported_pth)

    fmt_supported_glyphs: list = [
        f"    SMUFL_{gcode}_{gname} = 0x{gcode}," for gcode, gname in supported_glyphs.items()
    ]

    log.debug("SMuFL header will contain %s supported glyphs", len(fmt_supported_glyphs))
    fmt_glyph_list = "\n".join(fmt_supported_glyphs)
    fmt_header = SMUFL_HEADER.format(
        smufl_glyph_list=fmt_glyph_list, len_smufl_codes=len(fmt_supported_glyphs)
    )

    log.debug("Writing %s", header_file_pth)
    with open(header_file_pth, "w") as header_inc:
        header_inc.write(fmt_header)

    log.debug("Finished writing SMuFL header")
    return True


def extract_fonts(opts: Namespace) -> bool:
    """
    Takes a font file and extracts the necessary files for Verovio.
    Generates a glyph file for each glyph and a bounding-boxes file
    containing only the supported SMuFL glyphs.

    :param opts: A set of options from the argument parser sub-command.
    :return: True if successful, False otherwise.
    """
    fontname: str = opts.fontname

    source_pth: Path = Path(opts.source)
    font_data_pth: Path = Path(source_pth, fontname)
    metadata_pth: Path = Path(font_data_pth, f"{fontname.lower()}_metadata.json")
    font_pth: Path = Path(source_pth, font_data_pth, f"{fontname}.svg")
    data_pth: Path = Path(opts.data)
    glyph_file_pth: Path = Path(data_pth, fontname)
    output_pth: Path = Path(data_pth, f"{fontname}.xml")

    log.debug("Extracting fonts for %s from %s", fontname, font_data_pth.resolve())

    if not font_data_pth.is_dir() or not os.access(font_data_pth, os.R_OK):
        log.error("Could not read font information from %s", font_data_pth)
        return False

    if not os.access(metadata_pth, os.R_OK):
        log.error("Could not read %s. Does it exist?", metadata_pth)
        return False

    if not os.access(font_pth, os.R_OK):
        log.error("Could not read %s. Does it exist?", font_pth)
        return False

    if not os.access(data_pth, os.W_OK):
        log.error("Could not write to %s. Check permissions.", data_pth)
        return False

    if not glyph_file_pth.is_dir():
        log.debug("Creating %s", glyph_file_pth)
        glyph_file_pth.mkdir(parents=True)

    svg_data = __read_svg_font_file(str(font_pth))
    if not svg_data:
        log.error("Could not extract SVG data from %s", font_pth.resolve())
        return False

    family, units, hax, glyphs = svg_data

    log.debug(
        "SVG Data extracted: Family: %s, Units: %s, H-A-X: %s, Number of glyphs: %s",
        family,
        units,
        hax,
        len(glyphs),
    )

    supported_glyphs: dict = __combine_alternates_and_supported(opts)

    with open(metadata_pth, "r") as jfile:
        metadata: dict = json.load(jfile)

    __write_xml_glyphs(glyphs, supported_glyphs, units, glyph_file_pth)
    __write_bb_xml(glyphs, supported_glyphs, family, units, hax, metadata, output_pth)
    return True


def generate_css(opts: Namespace) -> bool:
    """
    Generates a CSS @font-face declaration for a given font.

    Builds a custom SVG font based on the glyphs specified in the
    "supported.xml" file, and the full SVG version of a given font.

    Base64-encodes the resulting WOFF2 font, and embeds it in a
    @font-face declaration.

    :param opts: A set of options from the argument parser sub-command.
    :return: True if successful, False otherwise.
    """
    fontname: str = opts.fontname

    source_pth: Path = Path(opts.source)
    font_data_pth: Path = Path(source_pth, fontname)
    font_pth: Path = Path(font_data_pth, f"{fontname}.svg")
    log.debug("Creating a subset SVG file from %s", font_pth.resolve())

    supported_glyphs: dict = __combine_alternates_and_supported(opts)

    log.debug("The resulting subset font will have %s glyphs", len(supported_glyphs.keys()))

    # Get the SVG source file's mtime for later...
    svg_mtime: float = font_pth.stat().st_mtime

    Et.register_namespace("", SVG_NS["svg"])
    svg_font: Et.ElementTree = Et.parse(str(font_pth))
    font_el: Optional[Et.Element] = svg_font.find(".//svg:defs/svg:font", SVG_NS)
    if not font_el:
        log.error("Could not find a font element in %s", font_pth.resolve())
        return False

    log.debug("Removing all hkern elements in since they are not needed.")
    for hkern in font_el.findall(".//svg:hkern", SVG_NS):
        font_el.remove(hkern)

    for glyph in font_el.findall(".//svg:glyph", SVG_NS):
        gname: Optional[str] = glyph.get("glyph-name")
        if gname and gname != "space" and gname[-4:] not in supported_glyphs:
            font_el.remove(glyph)

    log.debug("Shortening metadata entry to the essentials.")
    metadata_el: Optional[Et.Element] = svg_font.find(".//svg:metadata", SVG_NS)
    if metadata_el is not None:
        metadata_el.clear()
        metadata_el.text = B64_FONT_LICENSE.format(fontname=fontname)

    tmpdir = tempfile.mkdtemp()
    log.debug("Created temporary directory %s", tmpdir)

    tmp_svg_font = Path(tmpdir, f"{fontname}.svg")

    log.debug("Writing SVG font %s", tmp_svg_font.resolve())
    svg_font.write(str(tmp_svg_font), encoding="UTF-8", xml_declaration=True)

    tmp_woff2_pth: Optional[Path] = __fontforge_svg2woff(opts, tmpdir, svg_mtime)
    if not tmp_woff2_pth:
        log.error("Could not create WOFF2")
        return False

    css_filename: Path = Path(opts.data, f"{fontname}.css")

    with open(Path(tmpdir, f"{fontname}.woff2"), "rb") as woff2_content:
        b64_encoding: bytes = base64.b64encode(woff2_content.read())
        with open(css_filename, "w") as css_content:
            log.debug("Writing CSS file %s", css_filename.resolve())
            fmt_css: str = FONTFACE_WRAPPER.format(
                fontname=fontname, b64encoding=b64_encoding.decode()
            )
            css_content.write(fmt_css)

    if opts.keep_intermediates:
        intermediate_pth: Path = Path(font_data_pth, "tmp")
        log.debug("Keeping intermediate files in %s", intermediate_pth.resolve())
        intermediate_pth.mkdir(exist_ok=True)
        tmp_svg_font.replace(Path(intermediate_pth, f"{fontname}_subset.svg"))
        tmp_woff2_pth.replace(Path(intermediate_pth, f"{fontname}_subset.woff2"))

    log.debug("Removing temporary directory %s", tmpdir)
    shutil.rmtree(tmpdir)

    return True


def generate_svg(opts: Namespace) -> bool:
    """
    Generates a SVG font file from an input file using Fontforge.

    :param opts: A set of options from the argument parser sub-command.
    :return: True if successful, False otherwise.
    """
    convert_res: bool = __fontforge_convert(opts, "svg")
    if not convert_res:
        log.error("A problem happened with the fontforge conversion to SVG.")
        return False

    return True


def generate_woff2(opts: Namespace) -> bool:
    """
    Generates a WOFF2 file using Fontforge

    :param opts: A set of options from the argument parser sub-command.
    :return: True if successful, False otherwise.
    """
    convert_res: bool = __fontforge_convert(opts, "woff2")
    if not convert_res:
        log.error("A problem happened with the fontforge conversion to WOFF2.")
        return False

    return True


def check(opts: Namespace) -> bool:
    """
    Checks the glyphs of a font against the list of supported glyphs and identifies any glyphs
    that are missing in the font.

    :param opts: A set of options from the argument parser sub-command
    :return: True if successful, False otherwise
    """
    fontname: str = opts.fontname

    source_pth: Path = Path(opts.source)
    font_data_pth: Path = Path(source_pth, fontname)
    font_pth: Path = Path(font_data_pth, f"{fontname}.svg")

    all_glyphs: dict = __combine_alternates_and_supported(opts)

    Et.register_namespace("", SVG_NS["svg"])
    svg_font: Et.ElementTree = Et.parse(str(font_pth))
    glyphs: list[Et.Element] = svg_font.findall(".//svg:glyph", SVG_NS)
    glyph_names: list[str] = []
    for g in glyphs:
        if g is not None and (gn := g.get("glyph-name")):
            # space is not given as octal in svg fonts
            if gn == "space":
                gn = "0020"
            glyph_names.append(gn[-4:] if gn.startswith("uni") else gn)

    supported_codes: set = set(all_glyphs.keys())
    font_codes: set = set(glyph_names)

    supported_codes_not_in_font: set = supported_codes.difference(font_codes)
    font_codes_not_in_supported: set = font_codes.difference(supported_codes)

    sc: list[str] = sorted(list(supported_codes_not_in_font))
    fc: list[str] = sorted(list(font_codes_not_in_supported))
    print(f"Verovio-supported glyphs not in {fontname}: ", ", ".join(sc))
    if opts.show_unsupported:
        print(f"{fontname} glyphs not supported by Verovio: ", ", ".join(fc))

    return True


#########
# Private implementation methods.
#########
def __combine_alternates_and_supported(opts) -> dict:
    fontname: str = opts.fontname
    source_pth: Path = Path(opts.source)
    font_data_pth: Path = Path(source_pth, fontname)
    metadata_pth: Path = Path(font_data_pth, f"{fontname.lower()}_metadata.json")
    supported_glyphs: dict = __get_supported_glyph_codes(opts.supported)

    with open(metadata_pth, "r") as jsonfile:
        metadata: dict = json.load(jsonfile)

    if not os.access(metadata_pth, os.R_OK):
        log.warning("The metadata file could not be read at %s", metadata_pth)
        return supported_glyphs

    alternate_glyphs: dict = __get_alternate_glyphs(supported_glyphs, metadata)

    if alternate_glyphs:
        log.debug("Updating supported glyphs with alternates")
        supported_glyphs.update(alternate_glyphs)

    return supported_glyphs


def __check_fontforge(opts: Namespace) -> Optional[str]:
    fontforge_path: Optional[str] = (
        shutil.which("fontforge") if not opts.fontforge else opts.fontforge
    )
    if fontforge_path is None:
        log.error("Could not find fontforge. It is required for this operation.")
        return None

    if not os.access(fontforge_path, os.X_OK):
        log.error("%s does not point to an executable.", fontforge_path)
        return None

    log.debug("Found fontforge at %s", fontforge_path)
    return fontforge_path


def __fontforge_svg2woff(opts: Namespace, tmpdir: str, tstamp: float) -> Optional[Path]:
    fontforge_path: Optional[str] = __check_fontforge(opts)
    if not fontforge_path:
        return None

    fontforge_cmd: list = [fontforge_path, "-lang=py", "-"]

    tmp_svg = Path(tmpdir, f"{opts.fontname}.svg")
    if not os.access(tmp_svg, os.R_OK):
        log.error(
            "Could not read %s. It should exist, so something went wrong",
            tmp_svg.resolve(),
        )
        return None

    tmp_woff2 = Path(tmpdir, f"{opts.fontname}.woff2")

    ff_script: bytes = FONTFORGE_SCRIPT.format(
        input_fontpath=str(tmp_svg), output_fontpath=str(tmp_woff2)
    ).encode()

    subprocess_environment: dict = os.environ.copy()
    subprocess_environment["SOURCE_DATE_EPOCH"] = f"{tstamp}"

    log.debug("Fontforge script: %s", str(ff_script))

    try:
        _: subprocess.CompletedProcess = subprocess.run(
            fontforge_cmd, input=ff_script, check=True, env=subprocess_environment
        )
    except subprocess.CalledProcessError as e:
        log.error(
            "Fontforge exited with an error. Command: %s, Code: %s, Output: %s",
            e.cmd,
            e.returncode,
            e.output,
        )
        return None

    log.debug("WOFF2 file generated at %s", tmp_woff2.resolve())
    return tmp_woff2


def __fontforge_convert(opts: Namespace, fmt: str) -> bool:
    if fmt not in ("svg", "woff2"):
        log.error("Unknown conversion format %s. Must be either 'svg' or 'woff2'.", fmt)
        return False

    fontforge_path: Optional[str] = __check_fontforge(opts)
    if not fontforge_path:
        return False

    fontname: str = opts.fontname
    font_pth: Path = Path(opts.fontfile)

    font_mtime: float = font_pth.stat().st_mtime
    subprocess_environment: dict = os.environ.copy()
    subprocess_environment["SOURCE_DATE_EPOCH"] = font_mtime

    if not font_pth.is_file() or not os.access(font_pth, os.R_OK):
        log.error("Could not find or read %s.", font_pth)
        return False

    fontforge_cmd: list = [fontforge_path, "-lang=py", "-"]

    output_fontname: Path = Path(font_pth.parent, f"{fontname}.{fmt}")

    ff_script: bytes = FONTFORGE_SCRIPT.format(
        input_fontpath=str(font_pth), output_fontpath=str(output_fontname)
    ).encode()

    try:
        _: subprocess.CompletedProcess = subprocess.run(fontforge_cmd, input=ff_script, check=True)
    except subprocess.CalledProcessError as e:
        log.error(
            "Fontforge exited with an error. Command: %s, Code: %s, Output: %s",
            e.cmd,
            e.returncode,
            e.output,
        )
        return False

    log.debug("Converted %s to %s", font_pth.resolve(), output_fontname.resolve())
    return True


def __get_supported_glyph_codes(supported: Path) -> dict:
    """Retrieve dictionary with supported SMuFL codepoints and name."""
    log.debug("Getting supported glyph codes from %s", supported)
    supported_xml = Et.parse(str(supported))
    glyphs: list[Et.Element] = supported_xml.findall(".//glyph")

    log.debug("Found %s supported glyphs", len(glyphs))
    return {g.attrib["glyph-code"]: g.attrib["smufl-name"] for g in glyphs}


def __read_svg_font_file(
    fontfile: str,
) -> Optional[tuple[str, str, str, list[Et.Element]]]:
    font_xml: Et.ElementTree = Et.parse(fontfile)
    font_el: Optional[Et.Element] = font_xml.find("svg:defs/svg:font", SVG_NS)
    if not font_el:
        log.error("Could not find a font definition in %s.", fontfile)
        return None

    font_faces: list[Et.Element] = font_xml.findall(".//svg:font-face", SVG_NS)
    if len(font_faces) != 1:
        log.error("Error: the file %s should have a unique font-face element.", fontfile)
        log.error("Please check that the svg has correct namespace: %s.", SVG_NS["svg"])
        return None

    font_family: str = font_faces[0].attrib.get("font-family", "")
    units_per_em: str = font_faces[0].attrib.get("units-per-em", "")
    if not font_family or not units_per_em:
        log.error("Error: Could not find a font family or units-per-em definition.")
        return None

    default_hax = font_el.attrib.get("horiz-adv-x", "0")
    glyphs: list[Et.Element] = font_xml.findall(".//svg:glyph", SVG_NS)
    return font_family, units_per_em, default_hax, glyphs


def __write_xml_glyphs(
    glyphs: list[Et.Element],
    supported_glyphs: dict,
    units_per_em: str,
    output: Path,
) -> None:
    log.debug("Writing individual glyph files to %s", output.resolve())
    for glyph in glyphs:
        glyph_name: Optional[str] = glyph.attrib.get("glyph-name")
        if not glyph_name:
            log.debug("Could not find a glyph name. Skipping")
            continue

        # special treatment for space
        code: str = "0020" if glyph_name == "space" else glyph_name[-4:]
        if code not in supported_glyphs:
            log.debug("Glyph code %s is not supported. Skipping", code)
            continue

        rt: Et.Element = Et.Element("symbol")
        rt.set("id", code)
        rt.set("viewBox", f"0 0 {units_per_em} {units_per_em}")
        rt.set("overflow", "inherit")
        if "d" in glyph.attrib:
            pth = Et.SubElement(rt, "path")
            pth.set("transform", "scale(1,-1)")
            pth.set("d", glyph.attrib["d"])

        tr: Et.ElementTree = Et.ElementTree(rt)
        glyph_pth: Path = Path(output, f"{code}.xml")
        log.debug("Writing %s", glyph_pth.resolve())
        tr.write(str(glyph_pth), encoding="UTF-8")


def __write_bb_xml(
    glyphs: list[Et.Element],
    supported_glyphs: dict,
    family: str,
    units_per_em: str,
    default_hax: str,
    metadata: dict,
    output: Path,
) -> None:
    log.debug("Writing Verovio bounding-boxes file for %s", family)
    root: Et.Element = Et.Element("bounding-boxes")
    root.set("font-family", family)
    root.set("units-per-em", units_per_em)
    all_glyph_anchors: dict = metadata.get("glyphsWithAnchors", {})

    for glyph in glyphs:
        glyph_name: Optional[str] = glyph.attrib.get("glyph-name")
        if not glyph_name:
            log.debug("Could not find a glyph name. Skipping")
            continue

        # special treatment for space
        code: str = "0020" if glyph_name == "space" else glyph_name[-4:]
        if code not in supported_glyphs:
            continue

        g_element: Et.Element = Et.SubElement(root, "g")
        g_element.set("c", code)

        if "d" in glyph.attrib:
            svg_path = SvgPath(glyph.attrib["d"])
            xmin, xmax, ymin, ymax = svg_path.bbox()
            g_element.set("x", str(round(xmin, 2)))
            g_element.set("y", str(round(ymin, 2)))
            g_element.set("w", str(round(xmax - xmin, 2)))
            g_element.set("h", str(round(ymax - ymin, 2)))
        else:
            g_element.set("x", str(0.0))
            g_element.set("y", str(0.0))
            g_element.set("w", str(0.0))
            g_element.set("h", str(0.0))

        # set set horiz-av-x
        g_element.set("h-a-x", glyph.attrib.get("horiz-adv-x", default_hax))

        # Check if the value set for the "w" parameter can be converted to a float.
        # If not, set it to a default value. Somewhat complicated by also trying
        # to check if the element has an attribute of "w", or if it's None.
        try:
            wval: Optional[str] = g_element.get("w")
            if not wval:
                raise TypeError
            _ = float(wval)
        except TypeError:
            g_element.set("w", glyph.attrib.get("horiz-adv-x", default_hax))

        current_glyphname: Optional[str] = supported_glyphs.get(code)
        if current_glyphname:
            g_element.set("n", current_glyphname)
            g_anchors: dict = all_glyph_anchors.get(current_glyphname, {})
            for nm, anc in g_anchors.items():
                a_element = Et.SubElement(g_element, "a")
                a_element.set("n", nm)
                a_element.set("x", str(round(anc[0], 2)))
                a_element.set("y", str(round(anc[1], 2)))

    tree: Et.ElementTree = Et.ElementTree(root)
    Et.indent(tree)
    log.debug("Writing SVG file %s", output.resolve())
    tree.write(str(output), encoding="UTF-8", xml_declaration=True)


def __get_alternate_glyphs(glyphs: dict, metadata: dict) -> dict:
    glyph_alternates: dict = metadata.get("glyphsWithAlternates", {})
    inverted_glyphs: dict = {v: k for k, v in glyphs.items()}
    additional_glyphs: dict = {}

    for name, alternates in glyph_alternates.items():
        code: Optional[str] = inverted_glyphs.get(name)
        if not code:
            continue

        for alt in alternates["alternates"]:
            additional_glyphs[alt["codepoint"][2:]] = alt["name"]

    log.debug("Found %s alternate glyphs", len(additional_glyphs.keys()))
    return additional_glyphs


if __name__ == "__main__":
    cli = ArgumentParser()
    cli.add_argument("--debug", help="Run the command with debug output.", action="store_true")
    subparsers = cli.add_subparsers(help="[sub-command] help")
    supported_xml_help: str = "Path to a supported.xml file"
    smufl_description = """
    Extracts the supported glyphs from an SVG font file and creates the SMuFL header file for Verovio. 
    """
    parser_smufl = subparsers.add_parser("smufl", description=smufl_description)
    parser_smufl.add_argument("--supported", help=supported_xml_help, default="./supported.xml")
    parser_smufl.add_argument("--header-out", default="../include/vrv/")
    parser_smufl.set_defaults(func=generate_smufl)

    extract_description = """
    Extracts the supported glyphs from an SVG font file. Creates a new SVG font file, as well as individual SVG
    files for each glyph.
    """
    parser_extract = subparsers.add_parser("extract", description=extract_description)
    parser_extract.add_argument("fontname")
    parser_extract.add_argument("--supported", help=supported_xml_help, default="./supported.xml")
    parser_extract.add_argument(
        "--data", help="Path to the Verovio data directory", default="../data"
    )
    parser_extract.add_argument("--source", help="The font source parent directory", default="./")
    parser_extract.set_defaults(func=extract_fonts)

    css_description = """
    Creates a CSS definition of a subsetted font using FontForge. Also base64 encodes the WOFF2 output and wraps it 
    in a CSS @font-face definition.
    """

    fontname_help = "The name of the font. Sets the font-family in the CSS @font-face description."
    keep_help = """
    Keeps the intermediate SVG and WOFF2 font files saved to a tmp directory in the source directory. 
    Useful for debugging.
    """
    parser_css = subparsers.add_parser("css", description=css_description)
    parser_css.add_argument("fontname", help=fontname_help)
    parser_css.add_argument("--data", help="Path to the Verovio data directory", default="../data")
    parser_css.add_argument("--supported", help=supported_xml_help, default="./supported.xml")
    parser_css.add_argument("--source", help="The font source parent directory", default="./")
    parser_css.add_argument(
        "--fontforge",
        help="Path to fontforge binary (default is to auto-detect on the path)",
        default=None,
    )
    parser_css.add_argument("--keep-intermediates", help=keep_help, action="store_true")
    parser_css.set_defaults(func=generate_css)

    svg_description = """
    Creates an SVG font from any other font file supported by fontforge.
    """
    parser_svg = subparsers.add_parser("svg", description=svg_description)
    parser_svg.add_argument(
        "fontname",
        help="The name of the font. SVG files will be generated with this name",
    )
    parser_svg.add_argument(
        "fontfile",
        help="The path to the source font file. Can be any font file supported by fontforge.",
    )
    parser_svg.add_argument(
        "--fontforge",
        help="Path to fontforge binary (default is to auto-detect on the path)",
        default=None,
    )
    parser_svg.set_defaults(func=generate_svg)

    woff2_description = """
    Creates a WOFF2 font from any other font file supported by fontforge.
    """
    parser_woff2 = subparsers.add_parser("woff2", description=woff2_description)
    parser_woff2.add_argument(
        "fontname",
        help="The name of the font. SVG files will be generated with this name",
    )
    parser_woff2.add_argument(
        "fontfile",
        help="The path to the source font file. Can be any font file supported by fontforge.",
    )
    parser_woff2.add_argument(
        "--fontforge",
        help="Path to fontforge binary (default is to auto-detect on the path)",
        default=None,
    )
    parser_woff2.set_defaults(func=generate_woff2)

    check_description: str = """
    Checks the supported.xml file against a specified font, and reports on the glyphs that are supported
    by Verovio, but that are not in that font.
    
    Optionally, with the use of the `--show-unsupported` flag, will also show the list of glyphs that are in
    the font that are not supported by Verovio.
    """
    unsupported_help: str = (
        "Also show a list of glyphs in the font that are not supported by Verovio."
    )
    parser_check = subparsers.add_parser(
        "check", description=check_description, formatter_class=RawTextHelpFormatter
    )
    parser_check.add_argument("fontname", help=fontname_help)
    parser_check.add_argument("--supported", help=supported_xml_help, default="./supported.xml")
    parser_check.add_argument("--source", help="The font source parent directory", default="./")
    parser_check.add_argument("--show-unsupported", help=unsupported_help, action="store_true")

    parser_check.set_defaults(func=check)

    cmd_opts: Namespace = cli.parse_args()

    if cmd_opts.debug:
        LOGLEVEL = logging.DEBUG
    else:
        LOGLEVEL = logging.WARNING

    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)",
        level=LOGLEVEL,
    )

    res: bool = cmd_opts.func(cmd_opts)

    if not res:
        log.error("An error has occurred.")
        sys.exit(1)

    sys.exit(0)