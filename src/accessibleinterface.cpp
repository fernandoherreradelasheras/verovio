/////////////////////////////////////////////////////////////////////////////
// Name:        accessibleinterface.cpp
// Author:      Fernando Herrera de las Heras
// Created:     2026
// Copyright (c) Authors and others. All rights reserved.
/////////////////////////////////////////////////////////////////////////////

#include "accessibleinterface.h"

//----------------------------------------------------------------------------

#include "object.h"

namespace vrv {

//----------------------------------------------------------------------------
// AccessibleInterface
//----------------------------------------------------------------------------

AccessibleInterface::AccessibleInterface() {}

AccessibleInterface::~AccessibleInterface() {}

void AccessibleInterface::Reset() {}

std::string AccessibleInterface::GetAccessibleTitlte() const
{
    return "";
}

bool AccessibleInterface::GetAriaHidden() const
{
    return false;
}

} // namespace vrv
