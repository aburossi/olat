import streamlit as st
from openai import OpenAI
import json
import random
import PyPDF2
import docx
import re
import base64
from pdf2image import convert_from_bytes
import io
from PIL import Image
import logging
import httpx
import os

# Set page title and icon
st.set_page_config(page_title="OLAT Fragen Generator", page_icon="📝", layout="centered")

# Set up logging for better error tracking
logging.basicConfig(level=logging.INFO)

# Clear any existing proxy environment variables to prevent OpenAI SDK from using them
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

# Initialize a custom httpx client without proxies
http_client = httpx.Client()

# Initialize OpenAI client with the custom httpx client
client = OpenAI(
    api_key=st.secrets["openai"]["api_key"],  # API key from Streamlit Secrets
    http_client=http_client
)

# List of available message types
MESSAGE_TYPES = [
    "single_choice",
    "multiple_choice1",
    "multiple_choice2",
    "multiple_choice3",
    "kprim",
    "truefalse",
    "draganddrop",
    "inline_fib"
]

@st.cache_data
def read_prompt_from_md(filename):
    """Read the prompt from a markdown file and cache the result."""
    with open(f"{filename}.md", "r") as file:
        return file.read()

def process_image(_image):
    """Process and resize an image to reduce memory footprint."""
    if isinstance(_image, (str, bytes)):
        img = Image.open(io.BytesIO(base64.b64decode(_image) if isinstance(_image, str) else _image))
    elif isinstance(_image, Image.Image):
        img = _image
    else:
        img = Image.open(_image)

    # Convert to RGB mode if it's not
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize if the image is too large
    max_size = 1000  # Reduced max size to reduce memory consumption
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size))

    # Save to bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr = img_byte_arr.getvalue()

    return base64.b64encode(img_byte_arr).decode('utf-8')

def replace_german_sharp_s(text):
    """Replace all occurrences of 'ß' with 'ss'."""
    return text.replace('ß', 'ss')


def clean_json_string(s):
    s = s.strip()
    s = re.sub(r'^```json\s*', '', s)
    s = re.sub(r'\s*```$', '', s)
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'(?<=text": ")(.+?)(?=")', lambda m: m.group(1).replace('\n', '\\n'), s)
    s = ''.join(char for char in s if ord(char) >= 32 or char == '\n')
    match = re.search(r'\[.*\]', s, re.DOTALL)
    return match.group(0) if match else s

def convert_json_to_text_format(json_input):
    if isinstance(json_input, str):
        data = json.loads(json_input)
    else:
        data = json_input

    fib_output = []
    ic_output = []

    for item in data:
        text = item.get('text', '')
        blanks = item.get('blanks', [])
        wrong_substitutes = item.get('wrong_substitutes', [])

        num_blanks = len(blanks)

        fib_lines = [
            "Type\tFIB",
            "Title\t✏✏Vervollständigen Sie die Lücken mit dem korrekten Begriff.✏✏",
            f"Points\t{num_blanks}"
        ]

        for blank in blanks:
            text = text.replace(blank, "{blank}", 1)

        parts = text.split("{blank}")
        for index, part in enumerate(parts):
            fib_lines.append(f"Text\t{part.strip()}")
            if index < len(blanks):
                fib_lines.append(f"1\t{blanks[index]}\t20")

        fib_output.append('\n'.join(fib_lines))

        ic_lines = [
            "Type\tInlinechoice",
            "Title\tWörter einordnen",
            "Question\t✏✏Wählen Sie die richtigen Wörter.✏✏",
            f"Points\t{num_blanks}"
        ]

        all_options = blanks + wrong_substitutes
        random.shuffle(all_options)

        for index, part in enumerate(parts):
            ic_lines.append(f"Text\t{part.strip()}")
            if index < len(blanks):
                options_str = '|'.join(all_options)
                ic_lines.append(f"1\t{options_str}\t{blanks[index]}\t|")

        ic_output.append('\n'.join(ic_lines))

    return '\n\n'.join(fib_output), '\n\n'.join(ic_output)

def transform_output(json_string):
    try:
        cleaned_json_string = clean_json_string(json_string)
        json_data = json.loads(cleaned_json_string)
        fib_output, ic_output = convert_json_to_text_format(json_data)
        
        # Apply the cleaning function here
        fib_output = replace_german_sharp_s(fib_output)
        ic_output = replace_german_sharp_s(ic_output)

        return f"{ic_output}\n---\n{fib_output}"
    except json.JSONDecodeError as e:
        st.error(f"Error parsing JSON: {e}")
        st.text("Cleaned input:")
        st.code(cleaned_json_string, language='json')
        st.text("Original input:")
        st.code(json_string)
        
        try:
            if not cleaned_json_string.strip().endswith(']'):
                cleaned_json_string += ']'
            partial_json = json.loads(cleaned_json_string)
            st.warning("Attempted to salvage partial JSON. Results may be incomplete.")
            fib_output, ic_output = convert_json_to_text_format(partial_json)
            return f"{ic_output}\n---\n{fib_output}"
        except Exception as e_partial:
            st.error(f"Unable to salvage partial JSON: {e_partial}")
            return "Error: Invalid JSON format"
    except Exception as e:
        st.error(f"Error processing input: {str(e)}")
        st.text("Original input:")
        st.code(json_string)
        return "Error: Unable to process input"


def get_chatgpt_response(prompt, image=None, selected_language="English"):
    """Fetch response from OpenAI GPT with error handling."""
    try:
        # Step 2: Create a system prompt that includes language instruction
        system_prompt = (
            """
            You are an expert educator specializing in generating test questions and answers across all topics, following Bloom’s Taxonomy. Your role is to create high-quality Q&A sets based on the material provided by the user, ensuring each question aligns with a specific level of Bloom’s Taxonomy: Remember, Understand, Apply, Analyze, Evaluate, and Create.

            The user will provide input by either uploading a text or an image. Your tasks are as follows:

            Input Analysis:
            carefully analyze the content to understand the key concepts and important information.
            For Images: Strictly adhere to MAIN INSTRUCTIONS
            
            Question Generation by Bloom Level:
            Based on the analyzed material (from text or image), generate questions across all six levels of Bloom’s Taxonomy:

            Remember: Simple recall-based questions.
            Understand: Questions that assess comprehension of the material.
            Apply: Questions requiring the use of knowledge in practical situations.
            Analyze: Questions that involve breaking down the material and examining relationships.
            Evaluate: Critical thinking questions requiring judgments or assessments.
            Create: Open-ended tasks that prompt the student to design or construct something based on the information provided.
            """
        )
        
        if image:
            base64_image = process_image(image)
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low"
                            }
                        }
                    ]
                }
            ]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=16000,
            temperature=0.6
        )
        
        # Return the content of the first choice
        return response.choices[0].message.content
    except Exception as e:
        # Log and show error
        st.error(f"Error communicating with OpenAI API: {e}")
        logging.error(f"Error communicating with OpenAI API: {e}")
        return None

def process_images(images, selected_language):
    """Process uploaded images and generate questions."""
    for idx, image in enumerate(images):
        st.image(image, caption=f'Page {idx+1}', use_column_width=True)

        # Text area for user input and learning goals
        user_input = st.text_area(f"Enter your question or instructions for Page {idx+1}:", key=f"text_area_{idx}")
        learning_goals = st.text_area(f"Learning Goals for Page {idx+1} (Optional):", key=f"learning_goals_{idx}")
        selected_types = st.multiselect(f"Select question types for Page {idx+1}:", MESSAGE_TYPES, key=f"selected_types_{idx}")

        # Button to generate questions for the page
        if st.button(f"Generate Questions for Page {idx}", key=f"generate_button_{idx}"):
            # Only generate questions if there is user input and selected question types
            if user_input and selected_types:
                # Pass the selected_language here
                generate_questions_with_image(user_input, learning_goals, selected_types, image, selected_language)
            else:
                st.warning(f"Please enter text and select question types for Page {idx+1}.")

def generate_questions_with_image(user_input, learning_goals, selected_types, image, selected_language):
    """Generate questions for the image and handle errors."""
    all_responses = ""
    generated_content = {}
    for msg_type in selected_types:
        prompt_template = read_prompt_from_md(msg_type)
        full_prompt = f"MAIN INSTRUCTIONS:\n{prompt_template}\n\nUser Input: {user_input}\n\nLearning Goals: {learning_goals}"
        try:
            response = get_chatgpt_response(full_prompt, image=image, selected_language=selected_language)
            if response:
                if msg_type == "inline_fib":
                    processed_response = transform_output(response)
                    generated_content[f"{msg_type.replace('_', ' ').title()} (Processed)"] = processed_response
                    all_responses += f"{processed_response}\n\n"
                else:
                    generated_content[msg_type.replace('_', ' ').title()] = response
                    all_responses += f"{response}\n\n"
            else:
                st.error(f"Failed to generate a response for {msg_type}.")
        except Exception as e:
            st.error(f"An error occurred for {msg_type}: {str(e)}")
    
    # Apply cleaning function to all responses
    all_responses = replace_german_sharp_s(all_responses)

    # Display generated content with checkmarks
    st.subheader("Generated Content:")
    for title in generated_content.keys():
        st.write(f"✔ {title}")

    # Download button for all responses
    if all_responses:
        st.download_button(
            label="Download All Responses",
            data=all_responses,
            file_name="all_responses.txt",
            mime="text/plain"
        )

@st.cache_data
def convert_pdf_to_images(file):
    """Convert PDF pages to images."""
    images = convert_from_bytes(file.read())
    return images

@st.cache_data
def extract_text_from_pdf(file):
    """Extract text from PDF using PyPDF2."""
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text.strip()

@st.cache_data
def extract_text_from_docx(file):
    """Extract text from DOCX file."""
    doc = docx.Document(file)
    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    return text.strip()

def process_pdf(file):
    text_content = extract_text_from_pdf(file)
    
    # If no text is found, assume it's a non-OCR PDF
    if not text_content or not is_pdf_ocr(text_content):
        st.warning("This PDF is not OCRed. Text extraction failed. Please upload an OCRed PDF.")
        return None, convert_pdf_to_images(file)  # Fallback to image processing
    else:
        return text_content, None

def main():
    """Main function for the Streamlit app."""
    st.title("OLAT Fragen Generator")

    # Step 1: Language selection using radio buttons
    st.subheader("Einstellungen")
    
    # Two-column layout
    col1, col2 = st.columns([1, 2])  # Adjust column widths if necessary
    
    # Left Column: Language selection
    with col1:
        st.markdown("### Sprache auswählen:")
        languages = {
            "German": "German",
            "English": "English",
            "French": "French",
            "Italian": "Italian",
            "Spanish": "Spanish"
        }
        selected_language = st.radio("Wählen Sie die Sprache für den Output:", list(languages.values()), index=0)
    
    # Right Column: Dropdowns
    with col2:
        # Other expandable sections below
        with st.expander("ℹ️ Kosteninformationen"):
            st.markdown('''
            <div class="custom-info">
                <ul>
                    <li>Die Nutzungskosten hängen von der <strong>Länge der Eingabe</strong> ab (zwischen $0,01 und $0,1).</li>
                    <li>Jeder ausgewählte Fragetyp kostet ungefähr $0,01.</li>
                </ul>
            </div>
            ''', unsafe_allow_html=True)
        
        with st.expander("✅ Fragetypen"):
            st.markdown('''
            <div class="custom-success">
                <strong>Multiple-Choice-Fragen:</strong>
                <ul>
                    <li>Alle Multiple-Choice-Fragen haben maximal <strong>3 Punkte</strong>.</li>
                    <li><strong>multiple_choice1</strong>: 1 von 4 richtigen Antworten = 3 Punkte</li>
                    <li><strong>multiple_choice2</strong>: 2 von 4 richtigen Antworten = 3 Punkte</li>
                    <li><strong>multiple_choice3</strong>: 3 von 4 richtigen Antworten = 3 Punkte</li>
                </ul>
                <p>Man kann die Punktzahl der Fragen im Editor später mit Ctrl+H suchen und ersetzen. Achtung: Punktzahl für korrekte Antworten UND maximale Punktzahl anpassen!</p>
            </div>
            ''', unsafe_allow_html=True)
            st.markdown('''
            <div class="custom-success">
                <strong>Inline/FIB-Fragen:</strong>
                <ul>
                    <li>Die <strong>Inline</strong>- und <strong>FiB</strong>-Fragen sind inhaltlich identisch.</li>
                    <li>FiB = Das fehlende Wort eingeben.</li>
                    <li>Inline = Das fehlende Wort auswählen.</li>
                </ul>
            </div>
            ''', unsafe_allow_html=True)
            st.markdown('''
            <div class="custom-success">
                <strong>Andere Fragetypen:</strong>
                <ul>
                    <li><strong>Einzelauswahl</strong>: 4 Antworten, 1 Punkt pro Frage.</li>
                    <li><strong>KPRIM</strong>: 4 Antworten, 5 Punkte (4/4 korrekt), 2,5 Punkte (3/4 korrekt), 0 Punkte (50 % oder weniger korrekt).</li>
                    <li><strong>Wahr/Falsch</strong>: 3 Antworten, 3 Punkte pro Frage.</li>
                    <li><strong>Drag & Drop</strong>: Variable Punkte.</li>
                </ul>
            </div>
            ''', unsafe_allow_html=True)
    
        with st.expander("⚠️ Warnungen"):
            st.markdown('''
            <div class="custom-warning">
                <ul>
                    <li><strong>Überprüfen Sie immer, ob die Gesamtpunktzahl = Summe der Punkte der richtigen Antworten ist.</strong></li>
                    <li><strong>Überprüfen Sie immer den Inhalt der Antworten.</strong></li>
                </ul>
            </div>
            ''', unsafe_allow_html=True)

        # Kontaktinformationen Expander
        with st.expander("📧 Kontaktinformationen"):
            st.markdown('''
            <div class="custom-info">
                <p>Wenn du Fragen oder Verbesserungsideen hast, kannst du mich gerne kontaktieren:</p>
                <ul>
                    <li><strong>Pietro Rossi</strong></li>
                    <li><strong>E-Mail:</strong> pietro.rossi[at]bbw.ch</li>
                </ul>
                <p>Ich freue mich über dein Feedback!</p>
            </div>
            ''', unsafe_allow_html=True)



    
    # File uploader section
    uploaded_file = st.file_uploader("Upload a PDF, DOCX, or image file", type=["pdf", "docx", "jpg", "jpeg", "png"])

    text_content = ""
    image_content = None
    images = []

    
    # Reset cache when a new file is uploaded
    if uploaded_file:
        st.cache_data.clear()  # This clears the cache to avoid previous cached values

    if uploaded_file is not None:
        if uploaded_file.type == "application/pdf":
            text_content = extract_text_from_pdf(uploaded_file)
            if text_content:
                st.success("Text aus PDF extrahiert. Sie können es nun im folgenden Textfeld bearbeiten. PDFs, die länger als 5 Seiten sind, sollten gekürzt werden.")
            else:
                images = convert_pdf_to_images(uploaded_file)
                st.success("PDF converted to images. You can now ask questions about each page.")
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text_content = extract_text_from_docx(uploaded_file)
            st.success("Text extracted successfully. You can now edit it in the text area below.")
        elif uploaded_file.type.startswith('image/'):
            image_content = Image.open(uploaded_file)
            st.image(image_content, caption='Uploaded Image', use_column_width=True)
            st.success("Image uploaded successfully. You can now ask questions about the image.")
        else:
            st.error("Unsupported file type. Please upload a PDF, DOCX, or image file.")

    # Process images if any, otherwise process text or image content
    if images:
        process_images(images, selected_language)  # Pass the selected_language here
    else:
        user_input = st.text_area("Enter your text or question about the image:", value=text_content)
        learning_goals = st.text_area("Learning Goals (Optional):")
        
        # Select question types to generate
        selected_types = st.multiselect("Select question types to generate:", MESSAGE_TYPES)
        
        # Custom CSS for light blue background in info callouts
        st.markdown(
            """
            <style>
            .custom-info {
                background-color: #e7f3fe;
                padding: 10px;
                border-radius: 5px;
                border-left: 6px solid #2196F3;
            }
            .custom-success {
                background-color: #d4edda;
                padding: 10px;
                border-radius: 5px;
                border-left: 6px solid #28a745;
            }
            .custom-warning {
                background-color: #fff3cd;
                padding: 10px;
                border-radius: 5px;
                border-left: 6px solid #ffc107;
            }
            </style>
            """, unsafe_allow_html=True
        )
        
        # Generate questions button
        if st.button("Generate Questions"):
            if (user_input or image_content) and selected_types:
                # Ensure that the selected_language is passed to the function
                generate_questions_with_image(user_input, learning_goals, selected_types, image_content, selected_language)              
            elif not user_input and not image_content:
                st.warning("Please enter some text, upload a file, or upload an image.")
            elif not selected_types:
                st.warning("Please select at least one question type.")


@st.cache_data
def is_pdf_ocr(text):
    """Placeholder function to determine if PDF is OCRed."""
    # Implement actual OCR detection logic if necessary
    # For now, return True to assume PDFs are OCRed
    return True

if __name__ == "__main__":
    main()
