"""Enums for the LPS system - these define the valid values for states and causes."""
from enum import Enum


class WorkItemState(str, Enum):
    """The six states a WorkItem can be in. No other states are allowed."""
    INTENT = "Intent"
    NOT_READY = "Not Ready"
    READY = "Ready"
    COMMITTED = "Committed"
    COMPLETE = "Complete"
    FAILED = "Failed"


class ConstraintStatus(str, Enum):
    """Binary status for constraints."""
    OPEN = "Open"
    CLEARED = "Cleared"


class CommitmentStatus(str, Enum):
    """Status of a commitment."""
    ACTIVE = "Active"
    COMPLETE = "Complete"
    FAILED = "Failed"


class PrimaryCause(str, Enum):
    """Primary causes for failure - kept minimal per constitution."""
    ACCESS = "Access"
    MATERIALS = "Materials"
    INFORMATION = "Information"
    RESOURCES = "Resources"
    PERMITS = "Permits"
    PLANT_OR_EQUIPMENT = "Plant or equipment"
    INTERFACES = "Interfaces"
    WEATHER = "Weather"
    OTHER = "Other"


class ReferencePlanSystem(str, Enum):
    """External planning systems that can be referenced (read-only)."""
    MSP = "MSP"
    P6 = "P6"
    OTHER = "Other"
