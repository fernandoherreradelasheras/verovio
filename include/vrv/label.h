/////////////////////////////////////////////////////////////////////////////
// Name:        label.h
// Author:      Laurent Pugin
// Created:     19/06/2017
// Copyright (c) Authors and others. All rights reserved.
/////////////////////////////////////////////////////////////////////////////

#ifndef __VRV_LABEL_H__
#define __VRV_LABEL_H__

#include "accessibleinterface.h"
#include "object.h"

namespace vrv {

//----------------------------------------------------------------------------
// Label
//----------------------------------------------------------------------------

/**
 * This class models the MEI <label> element.
 */
class Label : public Object, public AccessibleInterface, public TextListInterface {

public:
    /**
     * @name Constructors, destructors, and other standard methods
     * Reset method resets all attribute classes
     */
    ///@{
    Label();
    virtual ~Label();
    Object *Clone() const override { return new Label(*this); }
    void Reset() override;
    std::string GetClassName() const override { return "label"; }
    ///@}

    /**
     * @name Getter to interfaces
     */
    ///@{
    AccessibleInterface *GetAccessibleInterface() override { return vrv_cast<AccessibleInterface *>(this); }
    const AccessibleInterface *GetAccessibleInterface() const override
    {
        return vrv_cast<const AccessibleInterface *>(this);
    }
    ///@}

protected:
    std::string GetAccessibleTitlte() const override;

public:
    /**
     * @name Methods for adding allowed content
     */
    ///@{
    bool IsSupportedChild(ClassId classId) override;
    ///@}

    //----------//
    // Functors //
    //----------//

    /**
     * Interface for class functor visitation
     */
    ///@{
    FunctorCode Accept(Functor &functor) override;
    FunctorCode Accept(ConstFunctor &functor) const override;
    FunctorCode AcceptEnd(Functor &functor) override;
    FunctorCode AcceptEnd(ConstFunctor &functor) const override;
    ///@}

private:
    //
public:
    //
private:
    //
};

} // namespace vrv

#endif
