"""
PDF Knowledge Extractor
Extracts landslide knowledge from GSI/Kerala reports
"""
import os
from pathlib import Path
from typing import List, Dict
import re
from pypdf import PdfReader


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF using pypdf
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Extracted text as string
    """
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            print(f"  Extracting {num_pages} pages from {Path(pdf_path).name}...")
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
    
    except Exception as e:
        print(f"  Error reading {pdf_path}: {e}")
        return ""
    
    return text


def extract_relevant_sections(text: str) -> Dict[str, List[str]]:
    """
    Extract sections relevant to landslide analysis
    
    Categories:
    - Causes (why landslides occurred)
    - Soil properties (geotechnical data)
    - Slope data (angles, elevations)
    - Rainfall data
    - Recommendations
    """
    sections = {
        "causes": [],
        "soil_properties": [],
        "slope_data": [],
        "rainfall": [],
        "recommendations": []
    }
    
    # Split into sentences
    sentences = re.split(r'[.!?]\s+', text)
    
    # Keywords for each category
    keywords = {
        "causes": ["cause", "trigger", "factor", "due to", "because", "resulted from", "saturated", "failure"],
        "soil_properties": ["soil", "cohesion", "friction", "laterite", "clay", "texture", "geotechnical"],
        "slope_data": ["slope", "angle", "steep", "gradient", "elevation", "degree"],
        "rainfall": ["rain", "precipitation", "mm", "monsoon", "heavy rain"],
        "recommendations": ["recommend", "suggest", "should", "must", "evacuate", "monitor", "warning"]
    }
    
    for sentence in sentences:
        if len(sentence.strip()) < 20:  # Skip very short fragments
            continue
            
        sentence_lower = sentence.lower()
        
        for category, terms in keywords.items():
            if any(term in sentence_lower for term in terms):
                sections[category].append(sentence.strip())
    
    return sections


def process_pdf_directory(pdf_dir: str) -> Dict:
    """
    Process all PDFs in a directory and extract knowledge
    """
    pdf_dir_path = Path(pdf_dir)
    pdf_files = list(pdf_dir_path.glob("*.pdf"))
    
    print(f"\nFound {len(pdf_files)} PDF files to process\n")
    
    all_knowledge = {
        "causes": [],
        "soil_properties": [],
        "slope_data": [],
        "rainfall": [],
        "recommendations": []
    }
    
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")
        
        # Extract text
        text = extract_text_from_pdf(str(pdf_file))
        
        if not text:
            print(f"  Skipped (no text extracted)\n")
            continue
        
        # Extract relevant sections
        sections = extract_relevant_sections(text)
        
        # Aggregate
        for category in all_knowledge.keys():
            all_knowledge[category].extend(sections[category])
        
        print(f"  Extracted {sum(len(s) for s in sections.values())} relevant sentences\n")
    
    # Remove duplicates
    for category in all_knowledge.keys():
        all_knowledge[category] = list(set(all_knowledge[category]))
    
    return all_knowledge


def save_extracted_knowledge(knowledge: Dict, output_file: str):
    """
    Save extracted knowledge to a JSON file
    """
    import json
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(knowledge, f, indent=2, ensure_ascii=False)
    
    print(f"\nKnowledge base saved to: {output_file}")
    
    # Print summary
    print("\nExtraction Summary:")
    for category, items in knowledge.items():
        print(f"  {category}: {len(items)} unique sentences")


if __name__ == "__main__":
    # Process the training PDFs
    pdf_directory = "../training datasets/training pdfs"
    output_file = "extracted_knowledge.json"
    
    print("=" * 60)
    print("PDF Knowledge Extraction")
    print("=" * 60)
    
    knowledge = process_pdf_directory(pdf_directory)
    save_extracted_knowledge(knowledge, output_file)
    
    print("\nDone!")
