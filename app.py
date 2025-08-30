import gradio as gr
from analysis_engine_ui import process_text, proc_text_dummy

process_text = proc_text_dummy
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
    download_button = gr.DownloadButton(label="Download Result", value = 'test.txt', visible = False)
    
    res_path_glob = ''
    # Define the function to execute on button click
    def on_process_click(text):
        print("--proc stage")
        result_path = process_text(text)
        download_button.visible = True
        return result_path

    def dummy_output(dat):
        print(dat)
    
    # Wire up the process button to call `on_process_click`
    # gr_file = gr.File()
    process_button.click(on_process_click, inputs=text_input, outputs=download_button)

# Launch the app


app.launch()

