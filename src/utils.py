import subprocess
import tempfile
import os

TEMPLATE_NAME = os.path.join('assets','latex_cv_template_v0.tex')

def _latex_to_pdf(latex_string, output_pdf):
    # Create a temporary directory to store intermediate files
    with tempfile.TemporaryDirectory() as tempdir:
        # Define the path for the temporary .tex file
        tex_file_path = os.path.join(tempdir, "temp.tex")
        
        # Write the LaTeX string to the .tex file
        with open(tex_file_path, "w") as tex_file:
            tex_file.write(latex_string)
        
        # Run xelatex to compile the .tex file into a PDF
        try:
            # -output-directory specifies where the PDF should be created (tempdir)
            subprocess.run(
                ["xelatex", "-output-directory", tempdir, tex_file_path],
                check=True
            )
            
            # Move the generated PDF to the specified output path
            pdf_path = os.path.join(tempdir, "temp.pdf")
            if os.path.exists(pdf_path):
                os.rename(pdf_path, output_pdf)
                print(f"PDF generated successfully: {output_pdf}")
            else:
                print("Error: PDF was not generated.")
        except subprocess.CalledProcessError as e:
            print("Error compiling LaTeX:", e)


class DocSection:
    def __init__(self, section_title, doc_section_items):
        self.section_title = section_title
        self.doc_section_items = doc_section_items
    
    def get_latex(self):
        s = f'\\begin{{rSection}}{{{self.section_title}}}\n'
        for _i in self.doc_section_items:
            s += _i.get_latex() + '\n'
        s += '\\end{rSection}\n'
        return s

class DocSectionItem:
    def __init__(self, company, duration, position, text_items):
        self.company, self.duration, self.position, self.item_list =  company, duration, position, text_items
        self.notes = None

    def set_notes(self, notes):
        self.notes = notes
        
    def get_latex(self):
        s = f"  \\begin{{myrSubsection}}{{{self.company}}}{{{self.duration}}}{{{self.position}}}\n"
        for i in self.item_list:
            s += f'    \\item {i}'
            if self.notes is not None:
                s += f'\\pdfcomment{{{self.notes}}}'
            s += '\n'
        s += f'  \\end{{myrSubsection}}\n'
        return s


class FullCVDocument:
    def __init__(self, statement : str, experience_section : DocSection):
        self.statement, self.experience_section = statement, experience_section

    def make_latex(self):
        with open(TEMPLATE_NAME, 'r') as f:
            ff = f.read()

        ff = ff.replace('<statement>', self.statement)
        ff = ff.replace('<experience_section>', self.experience_section.get_latex())
        return ff

    def render_pdf(self, out_file):
        _latex_to_pdf(self.make_latex(), out_file)
