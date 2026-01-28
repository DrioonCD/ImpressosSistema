import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
import os
import shutil
import webbrowser
from datetime import datetime
from PIL import Image as PilImage, ImageGrab
import pytesseract
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# --- CONFIGURAÇÃO OCR (Tente ajustar o caminho se necessário) ---
# Tesseract precisa estar instalado no Windows
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Configuração Interface
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- BANCO DE DADOS (SQLite) ---
class Database:
    def __init__(self, db_file="documaster.db"):
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS impressos (
                id TEXT PRIMARY KEY,
                nome TEXT,
                categoria TEXT,
                origem TEXT,
                descricao TEXT,
                status TEXT,
                image_path TEXT,
                created_at TEXT,
                selecionado INTEGER DEFAULT 1
            )
        """)
        self.conn.commit()

    def add_item(self, data):
        try:
            self.cursor.execute("""
                INSERT INTO impressos (id, nome, categoria, origem, descricao, status, image_path, created_at, selecionado)
                VALUES (:id, :nome, :categoria, :origem, :descricao, :status, :image_path, :created_at, :selecionado)
            """, data)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro BD Insert: {e}")
            return False

    def update_item(self, data):
        try:
            self.cursor.execute("""
                UPDATE impressos 
                SET nome=:nome, categoria=:categoria, origem=:origem, 
                    descricao=:descricao, status=:status, image_path=:image_path,
                    selecionado=:selecionado
                WHERE id=:id
            """, data)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro BD Update: {e}")
            return False

    def update_checkbox(self, item_id, selecionado):
        """Atualiza apenas o campo selecionado (checkbox)"""
        try:
            self.cursor.execute("UPDATE impressos SET selecionado=? WHERE id=?", (selecionado, item_id))
            self.conn.commit()
        except Exception as e:
            print(f"Erro BD Update Checkbox: {e}")

    def delete_item(self, item_id):
        self.cursor.execute("DELETE FROM impressos WHERE id=?", (item_id,))
        self.conn.commit()

    def get_all(self, search_term=""):
        if search_term:
            term = f"%{search_term}%"
            self.cursor.execute("""
                SELECT * FROM impressos 
                WHERE nome LIKE ? OR categoria LIKE ? OR origem LIKE ?
                ORDER BY created_at DESC
            """, (term, term, term))
        else:
            self.cursor.execute("SELECT * FROM impressos ORDER BY created_at DESC")
        
        # Converter tuplas para lista de dicionários
        columns = [column[0] for column in self.cursor.description]
        results = []
        for row in self.cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results

    def close(self):
        self.conn.close()


# --- GERADOR DE PDF ---
class ReportPDFGenerator:
    def __init__(self, filename):
        self.filename = filename
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        self.styles.add(ParagraphStyle(name='DocTitle', parent=self.styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1f538d'), alignment=1, spaceAfter=20))
        self.styles.add(ParagraphStyle(name='ItemHeader', parent=self.styles['Heading2'], fontSize=16, textColor=colors.HexColor('#2b2b2b'), borderPadding=5, backColor=colors.HexColor('#e8e8e8'), spaceBefore=15))
        # Estilos condicionais para status
        self.styles.add(ParagraphStyle(name='StatusRed', parent=self.styles['Normal'], textColor=colors.red, fontSize=10, fontName='Helvetica-Bold'))
        self.styles.add(ParagraphStyle(name='StatusGreen', parent=self.styles['Normal'], textColor=colors.green, fontSize=10, fontName='Helvetica-Bold'))
        self.styles.add(ParagraphStyle(name='StatusNormal', parent=self.styles['Normal'], textColor=colors.black, fontSize=10))

    def get_status_style(self, status):
        if status in ["Obsoleto", "Descontinuar"]: return self.styles['StatusRed']
        if status in ["Migrar para BI", "Modernizar"]: return self.styles['StatusGreen']
        return self.styles['StatusNormal']

    def generate(self, data_list):
        doc = SimpleDocTemplate(self.filename, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        story = []
        
        story.append(Spacer(1, 2 * inch))
        story.append(Paragraph("Documentação de Sistema - Relatório Analítico", self.styles['DocTitle']))
        story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", self.styles['Normal']))
        story.append(PageBreak())

        for item in data_list:
            header_text = f"{item['nome']} <font size=10 color=grey>({item['categoria']})</font>"
            story.append(Paragraph(header_text, self.styles['ItemHeader']))
            
            # Status Badge
            story.append(Paragraph(f"Status: {item['status']}", self.get_status_style(item['status'])))
            story.append(Spacer(1, 10))

            origem = item['origem'] if item['origem'] else "N/A"
            desc = item['descricao'] if item['descricao'] else "-"

            t = Table([
                [Paragraph("<b>Origem:</b>", self.styles['Normal']), Paragraph(origem, self.styles['Normal'])],
                [Paragraph("<b>Descrição:</b>", self.styles['Normal']), Paragraph(desc, self.styles['Normal'])]
            ], colWidths=[1.5*inch, 4.5*inch])
            
            t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LINEBELOW', (0,0), (-1,-1), 0.25, colors.lightgrey)]))
            story.append(t)
            story.append(Spacer(1, 10))

            if item['image_path'] and os.path.exists(item['image_path']):
                try:
                    img = PDFImage(item['image_path'])
                    aspect = img.imageHeight / float(img.imageWidth)
                    img.drawWidth = 6 * inch
                    img.drawHeight = 6 * inch * aspect
                    if img.drawHeight > 7*inch: # Limite altura
                         img.drawHeight = 7*inch
                         img.drawWidth = 7*inch / aspect
                    story.append(img)
                except: pass
            story.append(PageBreak())

        try:
            doc.build(story)
            return True
        except Exception as e:
            print(e)
            return False

# --- GERADOR DE WEBDOCS (HTML) ---
class WebDocsGenerator:
    def generate(self, data_list, output_folder="."):
        # Criar pasta de imagens direto na raiz escolhida
        images_web_folder = os.path.join(output_folder, "images")
        if not os.path.exists(images_web_folder):
            os.makedirs(images_web_folder)
            
        # Copiar imagens para a pasta "images"
        for item in data_list:
            if item['image_path'] and os.path.exists(item['image_path']):
                dest = os.path.join(images_web_folder, os.path.basename(item['image_path']))
                if not os.path.exists(dest):
                    shutil.copy(item['image_path'], dest)

        # Gerar index.html direto na raiz escolhida
        html_content = f"""
        <!DOCTYPE html>
        <html lang="pt-br">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Documentação do Sistema</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; overflow: hidden; display: flex; }}
                .card-img {{ width: 300px; height: 200px; object-fit: cover; background: #eee; cursor: pointer; }}
                .card-body {{ padding: 20px; flex: 1; }}
                .badge {{ padding: 5px 10px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: white; display: inline-block; margin-bottom: 10px;}}
                .bg-green {{ background-color: #27ae60; }}
                .bg-red {{ background-color: #c0392b; }}
                .bg-blue {{ background-color: #2980b9; }}
                .bg-grey {{ background-color: #7f8c8d; }}
                h2 {{ margin-top: 0; color: #2c3e50; }}
                .meta {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📚 Documentação de Impressos</h1>
                    <p>Total de itens: {len(data_list)} | Gerado em: {datetime.now().strftime('%d/%m/%Y')}</p>
                </div>
        """
        
        for item in data_list:
            status_color = "bg-grey"
            if item['status'] == "Migrar para BI": status_color = "bg-green"
            if item['status'] == "Obsoleto": status_color = "bg-red"
            if item['status'] == "Ativo": status_color = "bg-blue"

            img_src = ""
            if item['image_path']:
                img_src = f"images/{os.path.basename(item['image_path'])}"
            
            html_content += f"""
                <div class="card">
                    <img src="{img_src}" class="card-img" onclick="window.open('{img_src}', '_blank')">
                    <div class="card-body">
                        <span class="badge {status_color}">{item['status']}</span>
                        <h2>{item['nome']}</h2>
                        <div class="meta"><strong>Categoria:</strong> {item['categoria']} | <strong>Origem:</strong> {item['origem']}</div>
                        <p>{item['descricao']}</p>
                    </div>
                </div>
            """
            
        html_content += """
            </div></body></html>
        """
        
        # Salvar index.html direto na pasta escolhida
        with open(os.path.join(output_folder, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return os.path.abspath(os.path.join(output_folder, "index.html"))


# --- APLICAÇÃO PRINCIPAL ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DocuMaster Ultimate 2.0")
        self.geometry("1200x800")
        
        # Setup Diretórios e DB
        self.img_folder = "images_storage"
        if not os.path.exists(self.img_folder): os.makedirs(self.img_folder)
        self.db = Database()
        
        # Estado
        self.editing_item_id = None
        self.current_image_path = None
        self.check_vars = {} # {id: BooleanVar}

        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # PAINEL ESQUERDO (Formulário)
        self.left_frame = ctk.CTkFrame(self, width=400, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_propagate(False)

        # Header Form
        self.lbl_title_form = ctk.CTkLabel(self.left_frame, text="Novo Impresso", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title_form.pack(pady=(20, 10))

        # Campos
        self.entry_nome = self.create_input("Nome do Impresso (Título):")
        
        # Botão OCR (Pequeno, ao lado do nome seria ideal, mas vou por abaixo)
        self.btn_ocr = ctk.CTkButton(self.left_frame, text="🔍 Tentar Ler Título da Imagem (OCR)", 
                                     command=self.run_ocr, height=24, fg_color="#555", font=("Arial", 11))
        self.btn_ocr.pack(fill="x", padx=20, pady=(0, 10))

        self.entry_categoria = self.create_input("Categoria (ex: Financeiro):")
        
        # ComboBox Status
        ctk.CTkLabel(self.left_frame, text="Status Estratégico:", anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.combo_status = ctk.CTkComboBox(self.left_frame, values=["Ativo", "Migrar para BI", "Administrativo", "Obsoleto", "Redundante", "Revisar"])
        self.combo_status.pack(fill="x", padx=20, pady=5)
        
        self.entry_origem = self.create_input("Origem (Caminho Menu):")

        ctk.CTkLabel(self.left_frame, text="Descrição:", anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.txt_desc = ctk.CTkTextbox(self.left_frame, height=80)
        self.txt_desc.pack(fill="x", padx=20, pady=5)

        # Área de Imagem (Botões Lado a Lado)
        img_btn_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        img_btn_frame.pack(fill="x", padx=20, pady=15)
        
        self.btn_paste = ctk.CTkButton(img_btn_frame, text="📋 Colar Print (Ctrl+V)", command=self.paste_image, fg_color="#8e44ad", hover_color="#732d91", width=150)
        self.btn_paste.pack(side="left", padx=(0, 5), expand=True, fill="x")
        
        self.btn_file = ctk.CTkButton(img_btn_frame, text="📁 Arquivo", command=self.select_image_file, fg_color="#d35400", hover_color="#a04000", width=80)
        self.btn_file.pack(side="right", expand=True, fill="x")

        self.lbl_img_status = ctk.CTkLabel(self.left_frame, text="Sem imagem", text_color="grey")
        self.lbl_img_status.pack(pady=(0, 10))

        # Ações Finais
        self.btn_save = ctk.CTkButton(self.left_frame, text="Salvar Item", command=self.save_action, height=40, font=("Arial", 14, "bold"))
        self.btn_save.pack(fill="x", padx=20, pady=10)
        
        self.btn_cancel = ctk.CTkButton(self.left_frame, text="Cancelar Edição", command=self.cancel_edit, fg_color="transparent", border_width=1, text_color="grey")

        # Atalho Teclado
        self.bind("<Control-v>", lambda event: self.paste_image())


        # PAINEL DIREITO (Lista e Exportação)
        self.right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Header Direito
        top_bar = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(top_bar, text="Catálogo", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")

        # Barra de Busca
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_list)
        self.entry_search = ctk.CTkEntry(top_bar, placeholder_text="🔍 Buscar por nome, cat...", width=300, textvariable=self.search_var)
        self.entry_search.pack(side="right")

        # Lista
        self.scroll_frame = ctk.CTkScrollableFrame(self.right_frame, label_text="Itens Cadastrados")
        self.scroll_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Footer de Ações em Massa
        action_bar = ctk.CTkFrame(self.right_frame, height=50)
        action_bar.pack(fill="x")
        
        self.btn_pdf = ctk.CTkButton(action_bar, text="📄 Gerar PDF", command=self.generate_pdf, fg_color="#27ae60", hover_color="#219150")
        self.btn_pdf.pack(side="left", padx=10, pady=10)
        
        self.btn_web = ctk.CTkButton(action_bar, text="🌐 Gerar WebDocs (HTML)", command=self.generate_web, fg_color="#2980b9", hover_color="#1f618d")
        self.btn_web.pack(side="left", pady=10)

        # Inicializa Lista
        self.refresh_list()

    def create_input(self, label):
        ctk.CTkLabel(self.left_frame, text=label, anchor="w").pack(fill="x", padx=20, pady=(5, 0))
        entry = ctk.CTkEntry(self.left_frame)
        entry.pack(fill="x", padx=20, pady=5)
        return entry

    # --- LÓGICA DE IMAGEM & OCR ---
    def paste_image(self):
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, PilImage.Image):
                filename = f"temp_clipboard_{datetime.now().strftime('%M%S')}.png"
                temp_path = os.path.join(self.img_folder, filename)
                img.save(temp_path)
                self.current_image_path = temp_path
                self.lbl_img_status.configure(text="Imagem da Área de Transferência", text_color="#2ecc71")
            else:
                messagebox.showinfo("Info", "Nenhuma imagem encontrada na área de transferência.")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def select_image_file(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.png;*.jpg;*.jpeg")])
        if path:
            self.current_image_path = path
            self.lbl_img_status.configure(text=os.path.basename(path), text_color="#e67e22")

    def run_ocr(self):
        if not self.current_image_path:
            messagebox.showwarning("Aviso", "Cole ou anexe uma imagem primeiro.")
            return
        
        if not os.path.exists(TESSERACT_CMD):
            messagebox.showerror("Erro", "Tesseract não encontrado. Instale o Tesseract-OCR no Windows.")
            return

        try:
            img = PilImage.open(self.current_image_path)
            # Tesseract OCR
            text = pytesseract.image_to_string(img)
            # Tentar pegar a primeira linha não vazia como título
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                title_suggestion = lines[0] # Pega a primeira linha
                self.entry_nome.delete(0, "end")
                self.entry_nome.insert(0, title_suggestion)
                
                # Se tiver mais texto, joga na descrição (opcional)
                if len(lines) > 1:
                    desc_sug = "\n".join(lines[1:5]) # Pega mais 4 linhas
                    current_desc = self.txt_desc.get("1.0", "end-1c")
                    if not current_desc: # Só preenche se vazio
                        self.txt_desc.insert("1.0", f"Texto detectado:\n{desc_sug}")
            else:
                messagebox.showinfo("OCR", "Nenhum texto claro identificado.")
        except Exception as e:
            messagebox.showerror("Erro OCR", str(e))

    # --- LÓGICA CRUD ---
    def save_action(self):
        nome = self.entry_nome.get()
        if not nome:
            messagebox.showwarning("Erro", "Nome é obrigatório")
            return

        # Processar Imagem Final
        final_path = ""
        if self.current_image_path:
            # Se for imagem nova (temp ou arquivo externo), copia para storage definitivo
            if "temp_" in self.current_image_path or os.path.dirname(self.current_image_path) != self.img_folder:
                ext = os.path.splitext(self.current_image_path)[1]
                if not ext: ext = ".png"
                fname = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                final_path = os.path.join(self.img_folder, fname)
                try: shutil.copy(self.current_image_path, final_path)
                except: pass
            else:
                final_path = self.current_image_path

        data = {
            "nome": nome,
            "categoria": self.entry_categoria.get(),
            "origem": self.entry_origem.get(),
            "descricao": self.txt_desc.get("1.0", "end-1c"),
            "status": self.combo_status.get(),
            "image_path": final_path
        }

        if self.editing_item_id:
            # Se a imagem não mudou (None), precisamos manter a antiga
            if not self.current_image_path:
                # Busca a antiga no BD (não otimizado, mas seguro)
                # Na prática, deveríamos ter guardado o path antigo no start_edit
                pass 
                # (Correção simples: no start_edit eu guardo o path antigo se quiser manter, 
                # mas aqui vou assumir que se o user não mudou, o campo image_path deve ser preservado.
                # Como update_item sobrescreve, precisamos buscar o antigo se final_path for vazio)
            
            if not final_path:
                 # Gambiarra rápida: buscar o item antigo pra não perder a foto
                 items = self.db.get_all()
                 old = next((i for i in items if i['id'] == self.editing_item_id), None)
                 if old: data['image_path'] = old['image_path']

            data['id'] = self.editing_item_id
            self.db.update_item(data)
            self.cancel_edit()
        else:
            data['id'] = datetime.now().strftime('%Y%m%d%H%M%S')
            data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.db.add_item(data)
            self.clear_form()

        self.refresh_list()

    def filter_list(self, *args):
        term = self.search_var.get()
        self.refresh_list(term)

    def refresh_list(self, search_term=""):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        self.check_vars = {}
        
        items = self.db.get_all(search_term)
        
        for item in items:
            row = ctk.CTkFrame(self.scroll_frame)
            row.pack(fill="x", pady=2, padx=2)

            # Checkbox
            var = ctk.BooleanVar(value=bool(item.get('selecionado', 1)))
            self.check_vars[item['id']] = var
            ctk.CTkCheckBox(row, text="", variable=var, width=20, 
                            command=lambda i=item, v=var: self.db.update_checkbox(i['id'], 1 if v.get() else 0)).pack(side="left", padx=5)

            # Info
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, padx=5)
            
            # Status Color Marker
            color = "grey"
            if item['status'] == "Ativo": color = "#3498db"
            elif item['status'] == "Obsoleto": color = "#e74c3c"
            elif item['status'] == "Migrar para BI": color = "#2ecc71"
            
            ctk.CTkLabel(info, text=f"● {item['status']}", text_color=color, font=("Arial", 10, "bold")).pack(anchor="w")
            ctk.CTkLabel(info, text=item['nome'], font=("Arial", 12, "bold")).pack(anchor="w")
            ctk.CTkLabel(info, text=f"{item['categoria']}", text_color="grey", font=("Arial", 10)).pack(anchor="w")

            # Botões
            b_frame = ctk.CTkFrame(row, fg_color="transparent")
            b_frame.pack(side="right", padx=5)
            ctk.CTkButton(b_frame, text="✎", width=30, command=lambda i=item: self.start_edit(i)).pack(side="left", padx=2)
            ctk.CTkButton(b_frame, text="✖", width=30, fg_color="#c0392b", command=lambda i=item: self.delete_item(i)).pack(side="left")

    def start_edit(self, item):
        self.editing_item_id = item['id']
        self.clear_form()
        
        self.entry_nome.insert(0, item['nome'])
        self.entry_categoria.insert(0, item['categoria'])
        self.entry_origem.insert(0, item['origem'])
        self.txt_desc.insert("1.0", item['descricao'])
        self.combo_status.set(item['status'])
        
        if item['image_path']:
            self.lbl_img_status.configure(text=f"Imagem Mantida (Anexada)", text_color="#3498db")
            # Truque: setamos current como None pra lógica de 'manter' no save funcionar, 
            # mas visualmente mostramos que tem algo.
            self.current_image_path = None 
            
        self.lbl_title_form.configure(text="Editando Item", text_color="#3498db")
        self.btn_save.configure(text="Salvar Alterações")
        self.btn_cancel.pack(fill="x", padx=20, pady=5)

    def cancel_edit(self):
        self.editing_item_id = None
        self.clear_form()
        self.lbl_title_form.configure(text="Novo Impresso", text_color=["black", "white"])
        self.btn_save.configure(text="Salvar Item")
        self.btn_cancel.pack_forget()

    def clear_form(self):
        self.entry_nome.delete(0, "end")
        self.entry_categoria.delete(0, "end")
        self.entry_origem.delete(0, "end")
        self.txt_desc.delete("1.0", "end")
        self.combo_status.set("Ativo")
        self.current_image_path = None
        self.lbl_img_status.configure(text="Sem imagem", text_color="grey")

    def delete_item(self, item):
        if messagebox.askyesno("Confirmar", f"Excluir {item['nome']}?"):
            self.db.delete_item(item['id'])
            self.refresh_list(self.search_var.get())

    # --- EXPORTAÇÕES ---
    def generate_pdf(self):
        selected_ids = [k for k, v in self.check_vars.items() if v.get()]
        if not selected_ids: return
        
        # Pega itens do DB (poderia otimizar com query IN, mas vamos filtrar no python pra simplicidade)
        all_items = self.db.get_all()
        selected_items = [i for i in all_items if i['id'] in selected_ids]
        
        filename = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if filename:
            gen = ReportPDFGenerator(filename)
            if gen.generate(selected_items):
                os.startfile(filename)

    def generate_web(self):
        selected_ids = [k for k, v in self.check_vars.items() if v.get()]
        if not selected_ids: return
        
        all_items = self.db.get_all()
        selected_items = [i for i in all_items if i['id'] in selected_ids]
        
        folder = filedialog.askdirectory(title="Onde salvar a documentação Web?")
        if folder:
            target = os.path.join(folder, "WebDocs_Sistema")
            gen = WebDocsGenerator()
            index_path = gen.generate(selected_items, target)
            webbrowser.open(index_path)

if __name__ == "__main__":
    app = App()
    app.mainloop()