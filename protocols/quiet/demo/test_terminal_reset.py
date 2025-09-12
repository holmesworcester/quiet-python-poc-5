#!/usr/bin/env python3
"""Test script to verify terminal reset functionality."""

import subprocess
import sys
import os
import time

def test_terminal_state():
    """Check current terminal state."""
    # Test if mouse wheel scrolling is mapped to arrow keys
    print("Testing terminal state...")
    print("Try scrolling with mouse wheel - it should scroll the terminal, not send arrow keys")
    print("Try clicking in the terminal - mouse clicks should not be captured")
    print()

def main():
    print("=== Terminal Reset Test ===\n")
    
    # Show initial state
    print("1. Initial terminal state:")
    test_terminal_state()
    input("Press Enter to run demo in CLI mode...")
    
    # Run demo in CLI mode
    print("\n2. Running demo in CLI mode...")
    subprocess.run([sys.executable, "demo.py", "--cli", "--commands", "1:create alice", "1:list"])
    
    print("\n3. After CLI mode (terminal should be unchanged):")
    test_terminal_state()
    input("Press Enter to continue...")
    
    print("\n4. Setting terminal controls manually (simulating TUI)...")
    # Enable mouse tracking and alternate screen
    print("\033[?1049h", end="")  # Enter alternate screen
    print("\033[?1000h", end="")  # Enable mouse tracking
    print("\033[?1006h", end="")  # Enable SGR mouse mode
    print("\033[?1007h", end="")  # Enable alternate scroll mode
    sys.stdout.flush()
    
    print("Terminal controls enabled - mouse and scroll should be captured")
    time.sleep(2)
    
    print("\n5. Resetting terminal controls...")
    # Reset using same code as demo.py
    print("\033[?1000l", end="")  # Disable X11 mouse tracking
    print("\033[?1003l", end="")  # Disable all motion tracking  
    print("\033[?1015l", end="")  # Disable urxvt mouse mode
    print("\033[?1006l", end="")  # Disable SGR mouse mode
    print("\033[?1007l", end="")  # Disable alternate scroll mode
    print("\033[?1049l", end="")  # Exit alternate screen
    print("\033[?25h", end="")    # Show cursor
    print("\033[0m", end="")      # Reset all attributes
    sys.stdout.flush()
    
    print("\n6. Terminal should be back to normal:")
    test_terminal_state()
    
    print("\nTest complete!")

if __name__ == "__main__":
    main()