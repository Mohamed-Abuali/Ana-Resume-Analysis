from flask import request, jsonify, Flask, render_template
import fitz
from google import genai
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import re
import json  # Add this import

load_dotenv()

app = Flask(__name__, template_folder='app/templates', static_folder='app/static', static_url_path='/static')
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Define a proper schema that matches your prompt
class ResumeAnalysis(BaseModel):
    score: str
    strengths: str
    weaknesses: str
    suggestions: str  # Added to match your prompt

class ResumeMatcher(BaseModel):
    match:str
    missing:str
    score:str   

def extract_text_from_pdf(pdf_file):
    pdf_content = pdf_file.read()
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def ai_model(prompt, response_schema):
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": response_schema
        }
    )
    
    return response

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/enhance')
def enhance():
    return render_template('enhance.html')

@app.route('/matcher')
def mathcer():
    return render_template('matcher.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if "resume" not in request.files:
        return render_template('index.html', error="No file uploaded")

    file = request.files["resume"]
    if file.filename == '':
        return render_template('index.html', error="No file selected")
    
    if not file.filename.lower().endswith('.pdf'):
        return render_template('index.html', error="Please upload a PDF file")

    try:
        text = extract_text_from_pdf(file)
        if not text.strip():
            return render_template('index.html', error="Could not extract text from PDF")
        
        prompt = f"""Analyze the following resume and provide a JSON with:
        - score (as string with 0-100 / 100)
        - strengths (as string)
        - weaknesses (as string) 
        - suggestions (as string)
        
        Resume: {text}
        """

        # Use single Analyze model, not list
        response = ai_model(prompt, ResumeAnalysis)
        
        # Parse the response properly
        analysis_result = response.parsed  # This should be a ResumeAnalysis object
        
        # Convert to dict for template rendering
        result_dict = {
            "score": analysis_result.score,
            "strengths": analysis_result.strengths,
            "weaknesses": analysis_result.weaknesses,
            "suggestions": analysis_result.suggestions
        }
        
        return render_template('index.html', 
        score=result_dict["score"],
        strengths=result_dict["strengths"],
        weaknesses=result_dict["weaknesses"],
        suggestions=result_dict["suggestions"]
        )

    except Exception as e:
        return render_template('index.html', error=f"Error processing file: {str(e)}")

@app.route("/enhance_resume", methods=["POST"])
def enhance_resume():
    try:
        if "resume" not in request.files:
            return render_template('enhance.html', error="No file uploaded")
        
        file = request.files["resume"]
        if file.filename == '':
            return render_template('enhance.html', error="No file selected")
            
        plainText = extract_text_from_pdf(file)

        prompt = f"""
        Enhance this resume to pass Applicant Tracking Systems and highlight technical achievements.
        Return only the enhanced resume text.
        
        Resume: {plainText}
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        clean_text = re.sub(r'(^|\s)\*{1,3}(\s|$)', ' ', response.text)
       
        return render_template("enhance.html", result=clean_text)

    except Exception as e:
        return render_template("enhance.html", error=f"Error processing file: {str(e)}")


@app.route('/match_resume', methods=["POST"])
def match_resume():
    if "resume" not in request.files:
        return render_template('/mathcer.html',error="Please upload a PDF file")
    if "desc" not in request.form:
        return render_template('/matcher.html',error="Please file the job description")    
    try:
        file = request.files["resume"]
        job = request.form["desc"]
        text = extract_text_from_pdf(file)    
        if not text.strip():
            return render_template('/matcher.html', error="Could not extract the text from the file")

        prompt =f"""Write a match between a job description and a resume given dlimited by triple backticks extract the following what match with the resume, what missing in the resume , and the precentage on how much close between the job and the resume
        match:<what match>
        missing:<what is missing>
        score:<the precentage>
        
        job description {job}
        
        ```{text}```
        """

        response = ai_model(prompt,ResumeMatcher)   
        mathcer_result = response.parsed

        result = {
            "match":mathcer_result.match,
            "missing":mathcer_result.missing,
            "score":mathcer_result.score
        } 


        return render_template('/matcher.html', match=result["match"],
        missing=result["missing"],
        score=result["score"]
        )




    except ValueError:
        return render_template('/matcher.html',error=ValueError)    

if __name__ == '__main__':
    app.run(debug=True)