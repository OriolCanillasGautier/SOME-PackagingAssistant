import os
from fpdf import FPDF
from datetime import datetime

class ReportPDF(FPDF):
    def __init__(self, lang_code='cat_eng', logo_path='SOME.png'):
        super().__init__()
        self.lang_code = lang_code
        self.logo_path = logo_path
        self.set_auto_page_break(auto=True, margin=15)
        
        # Add a Unicode font for Polish/Spanish/Catalan support
        # Windows standard fonts path
        font_path = r'C:\Windows\Fonts\arial.ttf'
        if os.path.exists(font_path):
            self.add_font('ArialUni', '', font_path)
            self.current_font = 'ArialUni'
        else:
            self.current_font = 'helvetica'
        
        # Define translations
        self.strings = {
            'cat_eng': {
                'title': 'ESPECIFICACIONES PARA EXPEDICIONES / PACKAGING INSTRUCTIONS',
                'some_part': 'SOME Part Number:',
                'cust_part': 'Customer Part Number:',
                'description': 'Description:',
                'part_weight': 'Part Weight (Kg):',
                'customer': 'Customer:',
                'primary': 'PRIMARY PACKAGING',
                'secondary': 'SECONDARY PACKAGING',
                'pictures': 'PICTURES',
                'ref_cont': 'Referencia Contenedor:',
                'cont_ref': 'Container Reference:',
                'desc_med': 'Descripción y Medidas:',
                'desc_size': 'Description & Size:',
                'peso_neto': 'Peso Neto:',
                'net_weight': 'Net Weight:',
                'piezas_cont': 'Piezas por Contenedor:',
                'parts_cont': 'Parts per Container:',
                'peso_bruto': 'Peso Bruto:',
                'gross_weight': 'Gross Weight:',
                'otros': 'Otros Accesorios:',
                'others': 'Other Accessories:',
                'ref_palet': 'Referencia Palet:',
                'cont_palet': 'Containers per Palet:',
                'piezas_palet': 'Piezas por Palet:',
                'parts_palet': 'Parts per Palet:',
                'edited': 'Edited / Modified:',
                'revised': 'Revised:',
                'approved': 'Approved:',
                'footer': 'PACKAGING INSTRUCTIONS - 1st ED - Rev.01'
            },
            'eng': {
                'title': 'PACKAGING INSTRUCTIONS',
                'some_part': 'SOME Part Number:',
                'cust_part': 'Customer Part Number:',
                'description': 'Description:',
                'part_weight': 'Part Weight (Kg):',
                'customer': 'Customer:',
                'primary': 'PRIMARY PACKAGING',
                'secondary': 'SECONDARY PACKAGING',
                'pictures': 'PICTURES',
                'ref_cont': 'Container Reference:',
                'cont_ref': '',
                'desc_med': 'Description & Size:',
                'desc_size': '',
                'peso_neto': 'Net Weight:',
                'net_weight': '',
                'piezas_cont': 'Parts per Container:',
                'parts_cont': '',
                'peso_bruto': 'Gross Weight:',
                'gross_weight': '',
                'otros': 'Other Accessories:',
                'others': '',
                'ref_palet': 'Pallet Reference:',
                'cont_palet': 'Containers per Pallet:',
                'piezas_palet': 'Parts per Pallet:',
                'parts_palet': '',
                'edited': 'Edited / Modified:',
                'revised': 'Revised:',
                'approved': 'Approved:',
                'footer': 'PACKAGING INSTRUCTIONS - 1st ED - Rev.01'
            },
            'esp_eng': {
                'title': 'ESPECIFICACIONES PARA EXPEDICIONES / PACKAGING INSTRUCTIONS',
                'some_part': 'SOME Part Number:',
                'cust_part': 'Customer Part Number:',
                'description': 'Description:',
                'part_weight': 'Part Weight (Kg):',
                'customer': 'Customer:',
                'primary': 'PRIMARY PACKAGING',
                'secondary': 'SECONDARY PACKAGING',
                'pictures': 'PICTURES',
                'ref_cont': 'Referencia Contenedor:',
                'cont_ref': 'Container Reference:',
                'desc_med': 'Descripción y Medidas:',
                'desc_size': 'Description & Size:',
                'peso_neto': 'Peso Neto:',
                'net_weight': 'Net Weight:',
                'piezas_cont': 'Piezas por Contenedor:',
                'parts_cont': 'Parts per Container:',
                'peso_bruto': 'Peso Bruto:',
                'gross_weight': 'Gross Weight:',
                'otros': 'Otros Accesorios:',
                'others': 'Other Accessories:',
                'ref_palet': 'Referencia Palet:',
                'cont_palet': 'Containers per Palet:',
                'piezas_palet': 'Piezas por Palet:',
                'parts_palet': 'Parts per Palet:',
                'edited': 'Edited / Modified:',
                'revised': 'Revised:',
                'approved': 'Approved:',
                'footer': 'PACKAGING INSTRUCTIONS - 1st ED - Rev.01'
            },
            'pol_eng': {
                'title': 'SPECYFIKACJE DLA SPEDYCJI / PACKAGING INSTRUCTIONS',
                'some_part': 'SOME Part Number:',
                'cust_part': 'Customer Part Number:',
                'description': 'Opis / Description:',
                'part_weight': 'Waga części (Kg):',
                'customer': 'Klient / Customer:',
                'primary': 'OPAKOWANIE PODSTAWOWE / PRIMARY PACKAGING',
                'secondary': 'OPAKOWANIE ZBIORCZE / SECONDARY PACKAGING',
                'pictures': 'ZDJĘCIA / PICTURES',
                'ref_cont': 'Typ kontenera:',
                'cont_ref': 'Container Reference:',
                'desc_med': 'Opis i Wymiary:',
                'desc_size': 'Description & Size:',
                'peso_neto': 'Waga netto:',
                'net_weight': 'Net Weight:',
                'piezas_cont': 'Ilość części kontener:',
                'parts_cont': 'Parts per Container:',
                'peso_bruto': 'Waga Brutto:',
                'gross_weight': 'Gross Weight:',
                'otros': 'Inne akcesoria:',
                'others': 'Other Accessories:',
                'ref_palet': 'Typ kontenera:',
                'cont_palet': 'ilosc kontenerow na palecie:',
                'piezas_palet': 'ilosc czesci na palecie:',
                'parts_palet': 'Parts per Palet:',
                'edited': 'Edited / Modified:',
                'revised': 'Revised:',
                'approved': 'Approved:',
                'footer': 'PACKAGING INSTRUCTIONS - 1st ED - Rev.01'
            }
        }
        
    def get_str(self, key):
        return self.strings.get(self.lang_code, self.strings['cat_eng']).get(key, '')

    def header(self):
        # Logo and Title box
        if os.path.exists(self.logo_path):
            self.image(self.logo_path, 12, 12, 35)
        
        self.set_font(self.current_font, 'B', 12)
        # Vertical line after logo
        self.line(50, 10, 50, 25)
        
        # Title
        self.set_xy(50, 10)
        self.multi_cell(145, 5, self.get_str('title'), align='C')
        
        # Bold outer border for header
        self.set_line_width(0.5)
        self.rect(10, 10, 190, 15)
        
        # Part info section
        self.set_line_width(0.2)
        self.set_font(self.current_font, '', 9)
        
        y = 25
        # SOME Part Number | Customer Part Number
        self.rect(10, y, 95, 8)
        self.rect(105, y, 95, 8)
        self.set_xy(11, y + 2)
        self.write(4, self.get_str('some_part'))
        self.set_xy(106, y + 2)
        self.write(4, self.get_str('cust_part'))
        
        y += 8
        # Description | Part Weight | Customer
        self.rect(10, y, 95, 8)
        self.rect(105, y, 40, 8)
        self.rect(145, y, 55, 8)
        self.set_xy(11, y + 2)
        self.write(4, self.get_str('description'))
        self.set_xy(106, y + 2)
        self.write(4, self.get_str('part_weight'))
        self.set_xy(146, y + 2)
        self.write(4, self.get_str('customer'))
        
        self.ln(12)

    def draw_section_header(self, title):
        self.set_fill_color(240, 240, 240)
        self.set_font(self.current_font, 'BI', 10)
        self.cell(190, 6, title, border=1, ln=1, fill=True)

    def draw_data_row(self, label1, sublabel1, value1, unit1, label2, sublabel2, value2, label3, sublabel3, value3, unit3):
        start_y = self.get_y()
        col_w = [45, 80, 65]
        
        # Column 1
        self.rect(10, start_y, col_w[0], 15)
        self.set_font(self.current_font, '', 7)
        self.set_xy(11, start_y + 1)
        self.write(3, label1)
        if sublabel1:
            self.set_xy(11, start_y + 4)
            self.set_font(self.current_font, 'I', 7)
            self.write(3, sublabel1)
        
        self.set_font(self.current_font, 'B', 10)
        self.set_xy(35, start_y + 6)
        self.cell(15, 5, str(value1), border=1, align='C')
        self.set_font(self.current_font, '', 7)
        self.set_xy(50, start_y + 8)
        self.write(3, unit1)
        
        # Column 2
        self.rect(10 + col_w[0], start_y, col_w[1], 15)
        self.set_font(self.current_font, '', 7)
        self.set_xy(11 + col_w[0], start_y + 1)
        self.write(3, label2)
        if sublabel2:
            self.set_xy(11 + col_w[0], start_y + 4)
            self.set_font(self.current_font, 'I', 7)
            self.write(3, sublabel2)
        
        self.set_font(self.current_font, 'B', 9)
        self.set_xy( col_w[0] + 65, start_y + 3)
        self.cell(20, 10, value2, border=1, align='C')
        
        # Column 3
        self.rect(10 + col_w[0] + col_w[1], start_y, col_w[2], 15)
        self.set_font(self.current_font, '', 7)
        self.set_xy(11 + col_w[0] + col_w[1], start_y + 1)
        self.write(3, label3)
        if sublabel3:
            self.set_xy(11 + col_w[0] + col_w[1], start_y + 4)
            self.set_font(self.current_font, 'I', 7)
            self.write(3, sublabel3)
            
        self.set_font(self.current_font, 'B', 10)
        self.set_xy(165, start_y + 6)
        self.cell(25, 5, str(value3), border=1, align='C')
        self.set_font(self.current_font, '', 7)
        self.set_xy(191, start_y + 8)
        self.write(3, unit3)
        
        self.set_y(start_y + 15)

    def draw_accessories_row(self, label1, sublabel1, value1, label2, sublabel2, value2):
        start_y = self.get_y()
        col_w = [45, 55, 90]
        
        # Part 1 (Weight/Pieces)
        self.rect(10, start_y, col_w[0], 12)
        self.set_font(self.current_font, '', 7)
        self.set_xy(11, start_y + 1)
        self.write(3, label1)
        if sublabel1:
            self.set_xy(11, start_y + 4)
            self.set_font(self.current_font, 'I', 7)
            self.write(3, sublabel1)
        
        self.set_font(self.current_font, 'B', 9)
        self.set_xy(25, start_y + 3)
        self.cell(25, 7, str(value1), border=1, align='C')
        
        # Part 2 (Accessory label)
        self.rect(10 + col_w[0], start_y, col_w[1], 12)
        self.set_font(self.current_font, '', 7)
        self.set_xy(11 + col_w[0], start_y + 1)
        self.write(3, label2)
        if sublabel2:
            self.set_xy(11 + col_w[0], start_y + 4)
            self.set_font(self.current_font, 'I', 7)
            self.write(3, sublabel2)
            
        # Part 3 (Accessory value box)
        self.rect(10 + col_w[0] + col_w[1], start_y, col_w[2], 12)
        self.set_font(self.current_font, '', 7)
        self.set_xy(11 + col_w[0] + col_w[1], start_y + 2)
        self.multi_cell(88, 3, value2)
        
        self.set_y(start_y + 12)

    def generate_report(self, data, output_path):
        self.add_page()
        
        # Fill header data
        self.set_font(self.current_font, 'B', 10)
        self.set_xy(43, 27)
        self.write(4, data.get('some_part_number', ''))
        self.set_xy(145, 27)
        self.write(4, data.get('customer_part_number', ''))
        
        self.set_xy(30, 35)
        self.write(4, data.get('description', ''))
        self.set_xy(123, 35)
        self.write(4, str(data.get('part_weight', '')))
        self.set_xy(165, 35)
        self.write(4, data.get('customer_name', ''))
        
        # PRIMARY PACKAGING
        self.set_y(41)
        self.draw_section_header(self.get_str('primary'))
        self.draw_data_row(
            self.get_str('ref_cont'), self.get_str('cont_ref'), data.get('p_ref', ''), 'mm.',
            self.get_str('desc_med'), self.get_str('desc_size'), data.get('p_desc', ''),
            self.get_str('peso_neto'), self.get_str('net_weight'), data.get('p_net', ''), 'Kg.'
        )
        self.draw_accessories_row(
            self.get_str('piezas_cont'), self.get_str('parts_cont'), data.get('p_pieces', ''),
            self.get_str('otros'), self.get_str('others'), data.get('p_others', '')
        )
        self.draw_accessories_row(
            self.get_str('peso_bruto'), self.get_str('gross_weight'), data.get('p_gross', ''),
            '', '', '' # Spacer
        )
        
        # SECONDARY PACKAGING
        self.ln(2)
        self.draw_section_header(self.get_str('secondary'))
        self.draw_data_row(
            self.get_str('ref_palet'), '', data.get('s_ref', ''), 'mm.',
            self.get_str('desc_med'), self.get_str('desc_size'), data.get('s_desc', ''),
            self.get_str('peso_neto'), self.get_str('net_weight'), data.get('s_net', ''), 'Kg.'
        )
        self.draw_accessories_row(
            self.get_str('cont_palet'), '', data.get('s_containers', ''),
            self.get_str('piezas_palet'), '', data.get('s_pieces', '')
        )
        self.draw_accessories_row(
            self.get_str('peso_bruto'), '', data.get('s_gross', ''),
            self.get_str('otros'), self.get_str('others'), data.get('s_others', '')
        )
        
        # PICTURES
        self.ln(2)
        self.draw_section_header(self.get_str('pictures'))
        
        # Box for pictures
        pic_y_start = self.get_y()
        self.rect(10, pic_y_start, 190, 80)
        
        # Placeholder for 4 images
        images = data.get('images', []) # Expecting list of paths
        if len(images) > 0:
            # Layout images in a grid or row
            x_offsets = [15, 65, 115, 165]
            for i, img_path in enumerate(images[:4]):
                if os.path.exists(img_path):
                    self.image(img_path, x_offsets[i], pic_y_start + 5, 40)
        
        self.set_y(pic_y_start + 80)
        
        # Footer Approval table
        y_foot = 260
        col_w = 63
        self.set_font(self.current_font, '', 8)
        self.rect(10, y_foot, col_w, 10)
        self.set_xy(11, y_foot + 1)
        self.write(3, self.get_str('edited'))
        
        self.rect(10 + col_w, y_foot, col_w, 10)
        self.set_xy(11 + col_w, y_foot + 1)
        self.write(3, self.get_str('revised'))
        
        self.rect(10 + 2*col_w, y_foot, col_w, 10)
        self.set_xy(11 + 2*col_w, y_foot + 1)
        self.write(3, self.get_str('approved'))
        
        # Date and ED
        self.set_font(self.current_font, '', 6)
        self.set_xy(10, 275)
        self.write(3, self.get_str('footer'))
        self.set_xy(10, 278)
        self.write(3, f"Date: {datetime.now().strftime('%d/%m/%Y')} - Generated by PackAssist")
        
        self.output(output_path)

if __name__ == "__main__":
    # Test
    data = {
        'some_part_number': 'KTL51005636',
        'customer_part_number': '34222682A',
        'description': 'ANCHOR BRACKET APR1',
        'part_weight': 0.1040,
        'customer_name': 'TRW',
        'p_ref': '900',
        'p_desc': 'Contenedor Plástico B2',
        'p_net': 0.850,
        'p_pieces': 50,
        'p_gross': 6.050,
        'p_others': 'None',
        's_ref': '933',
        's_desc': 'Europalet',
        's_net': 23.00,
        's_containers': 56,
        's_pieces': 2800,
        's_gross': 361.800,
        's_others': 'Fleje Plástico, Plastic Strapping'
    }
    pdf = ReportPDF(lang_code='pol_eng', logo_path='SOME.png')
    pdf.generate_report(data, 'test_report.pdf')
    print("Test report generated: test_report.pdf")
