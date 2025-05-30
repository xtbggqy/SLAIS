import streamlit as st
from web.web_ui import run_slais_web_ui
from web.web_analysis import run_analysis
from web.web_results import display_results

def run_slais_web():
    ui_data = run_slais_web_ui()
    run_analysis(
        ui_data["analyze_button"],
        ui_data["article_doi"],
        ui_data["ncbi_email"],
        ui_data["pdf_path"],
        ui_data["pdf_stem"],
        ui_data["progress_bar"],
        ui_data["step_text"],
        ui_data["result_placeholder"]
    )
    display_results()

if __name__ == "__main__":
    run_slais_web()
