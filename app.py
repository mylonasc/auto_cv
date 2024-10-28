import gradio as gr
from analysis_engine_ui import process_text

# def process_text(text):
#     with open('')
#     # Process the input text (example: convert to uppercase)
#     processed_text = text.upper()
    
#     # Save processed text to a downloadable file
#     result_file_path = "/mnt/data/processed_result.txt"
#     with open(result_file_path, "w") as f:
#         f.write(processed_text)
    
#     return result_file_path

# Create the Gradio interface
with gr.Blocks() as app:
    # Textbox for user input
    text_input = gr.Textbox(label="Enter your text here", lines=10, placeholder="Type or paste your text here...")
    
    # Button to trigger processing
    process_button = gr.Button("Process Text")
    
    # Download button for the processed text file, hidden initially
    download_button = gr.File(label="Download Result", visible=False)
    
    # Define the function to execute on button click
    def on_process_click(text):
        result_path = process_text(text)
        # Make the download button visible with the processed file
        download_button.update(value=result_path, visible=True)
    
    # Wire up the process button to call `on_process_click`
    process_button.click(on_process_click, inputs=text_input, outputs=download_button)

# Launch the app
app.launch()

