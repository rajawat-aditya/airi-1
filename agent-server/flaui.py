import sys
import os
import subprocess
import time

dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deps', 'flaui')
sys.path.append(dll_path)

import clr
clr.AddReference('FlaUI.Core')
clr.AddReference('Interop.UIAutomationClient')
clr.AddReference('FlaUI.UIA3')

from FlaUI.UIA3 import UIA3Automation
from FlaUI.Core.Conditions import ConditionFactory
from FlaUI.Core.Definitions import ControlType
from FlaUI.UIA3 import UIA3PropertyLibrary

subprocess.Popen("notepad.exe")
time.sleep(2)

automation = UIA3Automation()
desktop = automation.GetDesktop()
cf = ConditionFactory(UIA3PropertyLibrary())

# find any window whose name contains "Notepad"
window = desktop.FindFirstDescendant(cf.ByName("Untitled - Notepad"))
if window is None:
    # Win11 notepad title may differ
    children = desktop.FindAllChildren()
    for child in children:
        if child.Name and "Notepad" in child.Name:
            window = child
            break

print(f"Window found: {window}")
print(f"Window Title: {window.Name}")
# Get all children of the window
children = window.FindAllChildren()
for child in children:
    print(child.ControlType, child.Name)

# Find the text area and type something
from FlaUI.Core.AutomationElements import AutomationElement
textbox = window.FindFirstDescendant(cf.ByControlType(ControlType.Document))
textbox.AsTextBox().Enter("Hello from FlaUI!")
automation.Dispose()
