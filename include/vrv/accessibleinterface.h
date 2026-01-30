/////////////////////////////////////////////////////////////////////////////
// Name:        accessibleinterface.h
// Author:      Fernando Herrera de las Heras
// Created:     2026
// Copyright (c) Authors and others. All rights reserved.
/////////////////////////////////////////////////////////////////////////////

#ifndef __VRV_ACCESSIBLE_INTERFACE_H__
#define __VRV_ACCESSIBLE_INTERFACE_H__

#include <string>

namespace vrv {

//----------------------------------------------------------------------------
// AccessibleInterface
//----------------------------------------------------------------------------

/**
 * SVG accessibility tree is build from the elements that are focusable or provide text content.or with text nly
 * elements with Browser accessibility tree is build with This class is an interface for elements implementing
 * accessibility support for the SVG output. Elements implementing this interface become focusable by default.  unless
 * support ARIA accessibility attributes. It is not an abstract class but should not be instanciated directly.
 */
class AccessibleInterface {
public:
    /**
     * @name Constructors, destructors, reset methods
     */
    ///@{
    AccessibleInterface();
    virtual ~AccessibleInterface();
    virtual void Reset();
    ///@}

    /**
     * @name Get accessibility title and description
     */
    ///@{
    virtual std::string GetAccessibleTitlte() const;
    virtual bool GetAriaHidden() const;
    ///@}
};

} // namespace vrv

#endif // __VRV_ACCESSIBLE_INTERFACE_H__
