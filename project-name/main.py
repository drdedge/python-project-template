#!/usr/bin/env python3
"""
Main entry point for the application
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()


def main():
    """Main function"""
    print("Hello from project-name!")
    
    # Example: Access environment variable
    debug_mode = os.getenv("DEBUG", "False").lower() == "true"
    if debug_mode:
        print("Running in debug mode")
    
    # Your application logic here
    

if __name__ == "__main__":
    main()