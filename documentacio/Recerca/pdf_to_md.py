import fitz  # pymupdf
import os

def pdf_to_markdown(pdf_path, md_path):
    """
    Converteix un PDF a Markdown
    """
    # Obrir el PDF
    doc = fitz.open(pdf_path)
    
    # Crear el fitxer Markdown
    with open(md_path, 'w', encoding='utf-8') as md_file:
        # Iterar per cada pàgina
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # Extreure el text
            text = page.get_text()
            
            # Escriure el text al fitxer Markdown
            md_file.write(f"# Pàgina {page_num + 1}\n\n")
            md_file.write(text)
            md_file.write("\n\n")
    
    doc.close()

if __name__ == "__main__":
    # Definir els paths
    pdf_dir = "."
    output_dir = "./md"
    
    # Crear el directori de sortida si no existeix
    os.makedirs(output_dir, exist_ok=True)
    
    # Llistar tots els PDFs
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
    
    # Convertir cada PDF a Markdown
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        md_file = os.path.splitext(pdf_file)[0] + ".md"
        md_path = os.path.join(output_dir, md_file)
        
        # Comprovar si el fitxer markdown ja existeix
        if os.path.exists(md_path):
            print(f"Saltant {pdf_file} - ja està convertit: {md_file}")
            continue
        
        print(f"Convertint {pdf_file} a {md_file}...")
        pdf_to_markdown(pdf_path, md_path)
        print(f"Conversió completada: {md_file}")