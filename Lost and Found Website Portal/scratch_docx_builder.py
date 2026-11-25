import os
import zipfile
import html

def escape_xml(s):
    if s is None:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))

class DocxBuilder:
    def __init__(self):
        self.paragraphs = []
        
    def add_page_break(self):
        self.paragraphs.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        
    def add_heading(self, text, level=1, align="left", page_break_before=False):
        sizes = {1: "36", 2: "28", 3: "24", 4: "22"}  # 18pt, 14pt, 12pt, 11pt
        colors = {1: "142B4A", 2: "1E40AF", 3: "1F2937", 4: "374151"}
        before_sp = {1: "360", 2: "240", 3: "180", 4: "120"}
        after_sp = {1: "180", 2: "120", 3: "80", 4: "60"}
        
        sz = sizes.get(level, "24")
        col = colors.get(level, "142B4A")
        bef = before_sp.get(level, "180")
        aft = after_sp.get(level, "80")
        
        jc = f'<w:jc w:val="{align}"/>' if align != "left" else ""
        pb = '<w:pageBreakBefore/>' if page_break_before else ''
        
        xml = f'''<w:p>
            <w:pPr>
                {pb}
                {jc}
                <w:spacing w:before="{bef}" w:after="{aft}"/>
            </w:pPr>
            <w:r>
                <w:rPr>
                    <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>
                    <w:b/>
                    <w:color w:val="{col}"/>
                    <w:sz w:val="{sz}"/>
                </w:rPr>
                <w:t xml:space="preserve">{escape_xml(text)}</w:t>
            </w:r>
        </w:p>'''
        self.paragraphs.append(xml)

    def add_paragraph(self, runs, align="both", before="0", after="120", line="276"):
        """
        runs is a list of tuples: (text, is_bold, is_italic, color, size, is_code)
        """
        jc = f'<w:jc w:val="{align}"/>' if align != "left" else ""
        run_xmls = []
        for item in runs:
            text = item[0]
            is_bold = item[1] if len(item) > 1 else False
            is_italic = item[2] if len(item) > 2 else False
            color = item[3] if len(item) > 3 and item[3] else "111827"
            size = item[4] if len(item) > 4 and item[4] else "24"  # 12pt
            is_code = item[5] if len(item) > 5 else False
            
            font = "Consolas" if is_code else "Times New Roman"
            b_tag = "<w:b/>" if is_bold else ""
            i_tag = "<w:i/>" if is_italic else ""
            shd_tag = '<w:shd w:val="clear" w:color="auto" w:fill="F3F4F6"/>' if is_code else ''
            
            r_xml = f'''<w:r>
                <w:rPr>
                    <w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>
                    {b_tag}
                    {i_tag}
                    <w:color w:val="{color}"/>
                    <w:sz w:val="{size}"/>
                    {shd_tag}
                </w:rPr>
                <w:t xml:space="preserve">{escape_xml(text)}</w:t>
            </w:r>'''
            run_xmls.append(r_xml)
            
        xml = f'''<w:p>
            <w:pPr>
                {jc}
                <w:spacing w:before="{before}" w:after="{after}" w:line="{line}" w:lineRule="auto"/>
            </w:pPr>
            {"".join(run_xmls)}
        </w:p>'''
        self.paragraphs.append(xml)

    def add_bullet(self, runs, level=0):
        indent = 360 * (level + 1)
        run_xmls = []
        for item in runs:
            text = item[0]
            is_bold = item[1] if len(item) > 1 else False
            is_italic = item[2] if len(item) > 2 else False
            color = item[3] if len(item) > 3 and item[3] else "111827"
            size = item[4] if len(item) > 4 and item[4] else "24"
            is_code = item[5] if len(item) > 5 else False
            
            font = "Consolas" if is_code else "Times New Roman"
            b_tag = "<w:b/>" if is_bold else ""
            i_tag = "<w:i/>" if is_italic else ""
            
            r_xml = f'''<w:r>
                <w:rPr>
                    <w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>
                    {b_tag}
                    {i_tag}
                    <w:color w:val="{color}"/>
                    <w:sz w:val="{size}"/>
                </w:rPr>
                <w:t xml:space="preserve">{escape_xml(text)}</w:t>
            </w:r>'''
            run_xmls.append(r_xml)
            
        xml = f'''<w:p>
            <w:pPr>
                <w:ind w:left="{indent}" w:hanging="240"/>
                <w:spacing w:before="40" w:after="60" w:line="260" w:lineRule="auto"/>
            </w:pPr>
            <w:r>
                <w:rPr>
                    <w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/>
                    <w:color w:val="2563EB"/>
                </w:rPr>
                <w:t>• </w:t>
            </w:r>
            {"".join(run_xmls)}
        </w:p>'''
        self.paragraphs.append(xml)

    def add_code_block(self, text):
        lines = text.strip().split("\n")
        rows = []
        for line in lines:
            rows.append(f'''<w:p>
                <w:pPr>
                    <w:spacing w:before="20" w:after="20" w:line="220" w:lineRule="auto"/>
                    <w:shd w:val="clear" w:color="auto" w:fill="F8FAFC"/>
                </w:pPr>
                <w:r>
                    <w:rPr>
                        <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
                        <w:color w:val="1E293B"/>
                        <w:sz w:val="19"/>
                    </w:rPr>
                    <w:t xml:space="preserve">{escape_xml(line)}</w:t>
                </w:r>
            </w:p>''')
        self.paragraphs.extend(rows)

    def add_table(self, headers, rows, col_widths=None):
        """
        headers: list of strings or tuples (text, is_bold)
        rows: list of lists of strings or tuples (text, is_bold, is_italic, color)
        col_widths: optional list of integer widths in dxa
        """
        tbl_pr = '''<w:tblPr>
            <w:tblW w:w="5000" w:type="pct"/>
            <w:tblBorders>
                <w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
                <w:left w:val="none"/>
                <w:bottom w:val="single" w:sz="8" w:space="0" w:color="64748B"/>
                <w:right w:val="none"/>
                <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
                <w:insideV w:val="none"/>
            </w:tblBorders>
        </w:tblPr>'''
        
        tr_list = []
        
        # Header Row
        th_cells = []
        for i, h in enumerate(headers):
            h_text = h if isinstance(h, str) else h[0]
            w_tag = f'<w:tcW w:w="{col_widths[i]}" w:type="dxa"/>' if col_widths and i < len(col_widths) else '<w:tcW w:w="0" w:type="auto"/>'
            th_cells.append(f'''<w:tc>
                <w:tcPr>
                    {w_tag}
                    <w:shd w:val="clear" w:color="auto" w:fill="1E3A8A"/>
                    <w:tcMar>
                        <w:top w:w="120" w:type="dxa"/>
                        <w:bottom w:w="120" w:type="dxa"/>
                        <w:left w:w="140" w:type="dxa"/>
                        <w:right w:w="140" w:type="dxa"/>
                    </w:tcMar>
                </w:tcPr>
                <w:p>
                    <w:pPr>
                        <w:spacing w:before="60" w:after="60"/>
                    </w:pPr>
                    <w:r>
                        <w:rPr>
                            <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>
                            <w:b/>
                            <w:color w:val="FFFFFF"/>
                            <w:sz w:val="22"/>
                        </w:rPr>
                        <w:t xml:space="preserve">{escape_xml(h_text)}</w:t>
                    </w:r>
                </w:p>
            </w:tc>''')
        tr_list.append(f'<w:tr><w:trPr><w:tblHeader/></w:trPr>{"".join(th_cells)}</w:tr>')
        
        # Body Rows
        for r_idx, row in enumerate(rows):
            td_cells = []
            bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            for c_idx, cell in enumerate(row):
                w_tag = f'<w:tcW w:w="{col_widths[c_idx]}" w:type="dxa"/>' if col_widths and c_idx < len(col_widths) else '<w:tcW w:w="0" w:type="auto"/>'
                
                # Check if cell is formatted or string
                if isinstance(cell, str):
                    c_text = cell
                    is_b = False
                    is_i = False
                    col = "1E293B"
                elif isinstance(cell, tuple):
                    c_text = cell[0]
                    is_b = cell[1] if len(cell) > 1 else False
                    is_i = cell[2] if len(cell) > 2 else False
                    col = cell[3] if len(cell) > 3 else "1E293B"
                else:
                    c_text = str(cell)
                    is_b, is_i, col = False, False, "1E293B"
                    
                b_xml = "<w:b/>" if is_b else ""
                i_xml = "<w:i/>" if is_i else ""
                
                # Multi-line in table cell support
                lines = c_text.split("\n")
                p_elements = []
                for l in lines:
                    p_elements.append(f'''<w:p>
                        <w:pPr>
                            <w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/>
                        </w:pPr>
                        <w:r>
                            <w:rPr>
                                <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>
                                {b_xml}
                                {i_xml}
                                <w:color w:val="{col}"/>
                                <w:sz w:val="21"/>
                            </w:rPr>
                            <w:t xml:space="preserve">{escape_xml(l)}</w:t>
                        </w:r>
                    </w:p>''')
                
                td_cells.append(f'''<w:tc>
                    <w:tcPr>
                        {w_tag}
                        <w:shd w:val="clear" w:color="auto" w:fill="{bg_color}"/>
                        <w:tcMar>
                            <w:top w:w="100" w:type="dxa"/>
                            <w:bottom w:w="100" w:type="dxa"/>
                            <w:left w:w="140" w:type="dxa"/>
                            <w:right w:w="140" w:type="dxa"/>
                        </w:tcMar>
                    </w:tcPr>
                    {"".join(p_elements)}
                </w:tc>''')
            tr_list.append(f'<w:tr>{"".join(td_cells)}</w:tr>')
            
        tbl_xml = f'<w:tbl>{tbl_pr}{"".join(tr_list)}</w:tbl>'
        self.paragraphs.append(tbl_xml)
        # Add small spacing after table
        self.paragraphs.append('<w:p><w:pPr><w:spacing w:before="60" w:after="100"/></w:pPr></w:p>')

    def build_docx(self, output_path):
        content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>'''

        root_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

        word_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>'''

        settings_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
</w:settings>'''

        styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
        <w:sz w:val="24"/>
        <w:szCs w:val="24"/>
        <w:lang w:val="en-US"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:before="0" w:after="120" w:line="276" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
</w:styles>'''

        doc_body = "".join(self.paragraphs)
        
        # Section properties: Standard Letter / A4 with 1-inch margins (1440 dxa)
        sect_pr = '''<w:sectPr>
            <w:pgSz w:w="12240" w:h="15840"/>
            <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
            <w:cols w:space="720"/>
            <w:docGrid w:linePitch="360"/>
        </w:sectPr>'''
        
        document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {doc_body}
    {sect_pr}
  </w:body>
</w:document>'''

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types_xml)
            z.writestr("_rels/.rels", root_rels_xml)
            z.writestr("word/_rels/document.xml.rels", word_rels_xml)
            z.writestr("word/settings.xml", settings_xml)
            z.writestr("word/styles.xml", styles_xml)
            z.writestr("word/document.xml", document_xml)

print("DocxBuilder class defined.")
