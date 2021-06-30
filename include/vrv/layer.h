/////////////////////////////////////////////////////////////////////////////
// Name:        layer.h
// Author:      Laurent Pugin
// Created:     2011
// Copyright (c) Authors and others. All rights reserved.
/////////////////////////////////////////////////////////////////////////////

#ifndef __VRV_LAYER_H__
#define __VRV_LAYER_H__

#include "atts_shared.h"
#include "drawinginterface.h"
#include "object.h"

namespace vrv {

class Clef;
class DeviceContext;
class LayerElement;
class Measure;
class Note;
class StaffDef;

//----------------------------------------------------------------------------
// Layer
//----------------------------------------------------------------------------

/**
 * This class represents a layer in a laid-out score (Doc).
 * A Layer is contained in a Staff.
 * It contains LayerElement objects.
 */
class Layer : public Object,
              public DrawingListInterface,
              public ObjectListInterface,
              public AttCue,
              public AttNInteger,
              public AttTyped,
              public AttVisibility {
public:
    /**
     * @name Constructors, destructors, and other standard methods
     * Reset method resets all attribute classes
     */
    ///@{
    Layer();
    virtual ~Layer();
    Object *Clone() const override { return new Layer(*this); }
    void Reset() override;
    std::string GetClassName() const override { return "Layer"; }
    ///@}

    /**
     * Overriding CloneReset() method to be called after copy / assignment calls.
     */
    void CloneReset() override;

    /**
     * @name Methods for adding allowed content
     */
    ///@{
    bool IsSupportedChild(Object *object) override;
    ///@}

    /**
     * Return the index position of the layer in its staff parent.
     * The index position is 0-based.
     */
    int GetLayerIdx() const { return Object::GetIdx(); }

    LayerElement *GetPrevious(LayerElement *element);
    LayerElement *GetAtPos(int x);
    LayerElement *Insert(LayerElement *element, int x); // return a pointer to the inserted element

    /**
     * Get the current clef for the test element.
     * Goes back on the layer until a clef is found.
     * This is used when inserting a note by passing a y position because we need
     * to know the clef in order to get the pitch.
     */
    Clef *GetClef(LayerElement *test);

    /**
     * Get the current clef based on facsimile for the test element.
     * This goes back by facsimile position until a clef is found.
     * Returns NULL if a clef cannot be found via this method.
     */
    Clef *GetClefFacs(LayerElement *test);

    /**
     * Return the clef offset for the position x.
     * The method uses Layer::GetClef first to find the clef before test.
     */
    int GetClefLocOffset(LayerElement *test);

    /**
     * Return the clef offset for the position if there are cross-staff clefs on the same layer
     */
    int GetCrossStaffClefLocOffset(LayerElement *element, int locOffset);

    /**
     * @name Set and get the stem direction of the layer.
     * This stays STEMDIRECTION_NONE with on single layer in the staff.
     */
    ///@{
    void SetDrawingStemDir(data_STEMDIRECTION stemDirection) { m_drawingStemDir = stemDirection; }
    data_STEMDIRECTION GetDrawingStemDir(LayerElement *element);
    data_STEMDIRECTION GetDrawingStemDir(const ArrayOfBeamElementCoords *coords);
    data_STEMDIRECTION GetDrawingStemDir() const { return m_drawingStemDir; }
    ///@}

    /**
     * @name Get the layers used for the duration of an element.
     * Takes into account cross-staff situations: cross staff layers have negative N.
     */
    ///@{
    std::set<int> GetLayersNForTimeSpanOf(LayerElement *element);
    int GetLayerCountForTimeSpanOf(LayerElement *element);
    ///@}

    /**
     * @name Get the layers used within a time span.
     * Takes into account cross-staff situations: cross staff layers have negative N.
     */
    ///@{
    std::set<int> GetLayersNInTimeSpan(double time, double duration, Measure *measure, int staff);
    int GetLayerCountInTimeSpan(double time, double duration, Measure *measure, int staff);
    ///@}

    /**
     * Get the list of the layer elements for the duration of an element
     * Takes into account cross-staff situations.
     * If excludeCurrent is specified, gets the list of layer elements for all layers except current
     */
    ListOfObjects GetLayerElementsForTimeSpanOf(LayerElement *element, bool excludeCurrent = false);

    /**
     * Get the list of the layer elements used within a time span.
     * Takes into account cross-staff situations.
     */
    ListOfObjects GetLayerElementsInTimeSpan(
        double time, double duration, Measure *measure, int staff, bool excludeCurrent);

    Clef *GetCurrentClef();
    KeySig *GetCurrentKeySig();
    Mensur *GetCurrentMensur();
    MeterSig *GetCurrentMeterSig();

    void ResetStaffDefObjects();

    /**
     * Set drawing clef, keysig and mensur if necessary and if available.
     */
    void SetDrawingStaffDefValues(StaffDef *currentStaffDef);

    bool DrawKeySigCancellation() const { return m_drawKeySigCancellation; }
    void SetDrawKeySigCancellation(bool drawKeySigCancellation) { m_drawKeySigCancellation = drawKeySigCancellation; }
    Clef *GetStaffDefClef() { return m_staffDefClef; }
    KeySig *GetStaffDefKeySig() { return m_staffDefKeySig; }
    Mensur *GetStaffDefMensur() { return m_staffDefMensur; }
    MeterSig *GetStaffDefMeterSig() { return m_staffDefMeterSig; }
    MeterSigGrp *GetStaffDefMeterSigGrp() { return m_staffDefMeterSigGrp; }
    bool HasStaffDef()
    {
        return (m_staffDefClef || m_staffDefKeySig || m_staffDefMensur || m_staffDefMeterSig || m_staffDefMeterSigGrp);
    }

    /**
     * Set drawing clef, keysig and mensur if necessary and if available.
     */
    void SetDrawingCautionValues(StaffDef *currentStaffDef);

    bool DrawCautionKeySigCancel() const { return m_drawCautionKeySigCancel; }
    void SetDrawCautionKeySigCancel(bool drawCautionKeySig) { m_drawCautionKeySigCancel = drawCautionKeySig; }
    Clef *GetCautionStaffDefClef() { return m_cautionStaffDefClef; }
    KeySig *GetCautionStaffDefKeySig() { return m_cautionStaffDefKeySig; }
    Mensur *GetCautionStaffDefMensur() { return m_cautionStaffDefMensur; }
    MeterSig *GetCautionStaffDefMeterSig() { return m_cautionStaffDefMeterSig; }
    bool HasCautionStaffDef()
    {
        return (
            m_cautionStaffDefClef || m_cautionStaffDefKeySig || m_cautionStaffDefMensur || m_cautionStaffDefMeterSig);
    }

    /**
     * @name Setter and getter for the cross-staff flags
     */
    //@{
    void SetCrossStaffFromAbove(bool crossStaff) { m_crossStaffFromAbove = crossStaff; }
    bool HasCrossStaffFromAbove() const { return m_crossStaffFromAbove; }
    void SetCrossStaffFromBelow(bool crossStaff) { m_crossStaffFromBelow = crossStaff; }
    bool HasCrossStaffFromBelow() const { return m_crossStaffFromBelow; }
    ///@}

    //----------//
    // Functors //
    //----------//

    /**
     * See Object::ConvertMarkupArtic
     */
    int ConvertMarkupArticEnd(FunctorParams *functorParams) override;

    /**
     * See Object::ConvertToCastOffMensural
     */
    int ConvertToCastOffMensural(FunctorParams *functorParams) override;

    /**
     * See Object::ConvertToUnCastOffMensural
     */
    int ConvertToUnCastOffMensural(FunctorParams *functorParams) override;

    /**
     * See Object::UnscoreDefSetCurrent
     */
    int ScoreDefUnsetCurrent(FunctorParams *functorParams) override;

    /**
     * See Object::ResetHorizontalAlignment
     */
    int ResetHorizontalAlignment(FunctorParams *functorParams) override;

    /**
     * See Object::AlignHorizontally
     */
    int AlignHorizontally(FunctorParams *functorParams) override;

    /**
     * See Object::AlignHorizontallyEnd
     */
    int AlignHorizontallyEnd(FunctorParams *functorParams) override;

    /**
     * See Object::InitProcessingLists
     */
    int InitProcessingLists(FunctorParams *functorParams) override;

    /**
     * See Object::PrepareRpt
     */
    int PrepareRpt(FunctorParams *functorParams) override;

    /**
     * See Object::InitOnsetOffset
     */
    ///@{
    int InitOnsetOffset(FunctorParams *functorParams) override;
    ///@}

    /**
     * See Object::ResetData
     */
    int ResetData(FunctorParams *functorParams) override;

    /**
     * @name See Object::GenerateMIDI
     */
    ///@{
    int GenerateMIDI(FunctorParams *functorParams) override;
    ///@}

    /**
     * See Object::GenerateMIDIEnd
     */
    int GenerateMIDIEnd(FunctorParams *functorParams) override;

private:
    //
public:
    //
private:
    /**
     * The drawing stem direction of the layer based on the number of layers in the staff
     */
    data_STEMDIRECTION m_drawingStemDir;

    /**
     * Two flags indicating when a layer is also used from cross-staff content from below or above
     */
    bool m_crossStaffFromBelow;
    bool m_crossStaffFromAbove;

    /** */
    Clef *m_staffDefClef;
    KeySig *m_staffDefKeySig;
    Mensur *m_staffDefMensur;
    MeterSig *m_staffDefMeterSig;
    MeterSigGrp *m_staffDefMeterSigGrp;
    bool m_drawKeySigCancellation;

    /** */
    Clef *m_cautionStaffDefClef;
    KeySig *m_cautionStaffDefKeySig;
    Mensur *m_cautionStaffDefMensur;
    MeterSig *m_cautionStaffDefMeterSig;
    bool m_drawCautionKeySigCancel;
};

} // namespace vrv

#endif
