import os

# Check if .env file exists and load it
if os.path.exists('.env'):
    from dotenv import load_dotenv
    load_dotenv()

import streamlit as st

def main():
    # This is just a wrapper to launch the streamlit app
    # The real UI code is in /interface/app.py
    # This wrapper is needed because the main streamlit script
    # expects the GOOGLE_API_KEY to be loaded, which isn't
    # guaranteed when the script is run.
    import interface.app

if __name__ == "__main__":
    main()