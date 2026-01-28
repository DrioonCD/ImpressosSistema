import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import shutil
from datetime import datetime
from PIL import Image as PilImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Configuração Inicial
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ReportPDFGenerator:
    def __init__(self, filename="Documentacao_Sistema.pdf"):
        self.filename = filename
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        # Estilo para Títulos
        self.styles.add(ParagraphStyle(
            name='DocTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f538d'),
            alignment=1,
            spaceAfter=20
        ))
        
        # Estilo para Cabeçalhos de Itens
        self.styles.add(ParagraphStyle(
            name='ItemHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2b2b2b'),
            borderPadding=5,
            backColor=colors.HexColor('#e8e8e8'),
            spaceBefore=15
        ))

    def generate(self, data_list):
        if not data_list:
            return False

        doc = SimpleDocTemplate(
            self.filename,
            pagesize=A4,
            rightMargin=50, leftMargin=50,
            topMargin=50, bottomMargin=50
        )

        story = []

        # Capa
        story.append(Spacer(1, 2 * inch))
        story.append(Paragraph("Documentação de Impressos do Sistema", self.styles['DocTitle']))
        story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", self.styles['Normal']))
        story.append(Paragraph(f"Total de Itens: {len(data_list)}", self.styles['Normal']))
        story.append(PageBreak())

        # Conteúdo
        for item in data_list:
            # Título do Item
            story.append(Paragraph(f"{item['nome']} <font size=10 color=grey>({item['categoria']})</font>", self.styles['ItemHeader']))
            story.append(Spacer(1, 10))

            # Tabela de Metadados
            # Proteção contra caracteres None ou vazios
            origem_texto = item['origem'] if item['origem'] else "N/A"
            desc_texto = item['descricao'] if item['descricao'] else "Sem descrição"

            table_data = [
                [Paragraph("<b>Origem/Caminho:</b>", self.styles['Normal']), Paragraph(origem_texto, self.styles['Normal'])],
                [Paragraph("<b>Descrição:</b>", self.styles['Normal']), Paragraph(desc_texto, self.styles['Normal'])]
            ]

            t = Table(table_data, colWidths=[1.5*inch, 4.5*inch])
            t.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(t)
            story.append(Spacer(1, 15))

            # Imagem
            if item['image_path'] and os.path.exists(item['image_path']):
                try:
                    # Redimensionamento inteligente mantendo aspect ratio
                    img = PDFImage(item['image_path'])
                    img_width = 6 * inch
                    aspect = img.imageHeight / float(img.imageWidth)
                    img.drawHeight = img_width * aspect
                    img.drawWidth = img_width
                    
                    # Limite de altura para não quebrar página feio se for muito comprida
                    if img.drawHeight > 8 * inch:
                        img.drawHeight = 8 * inch
                        img.drawWidth = (8 * inch) / aspect

                    story.append(Paragraph("<b>Captura de Tela:</b>", self.styles['Normal']))
                    story.append(Spacer(1, 5))
                    story.append(img)
                except Exception as e:
                    story.append(Paragraph(f"<i>Erro ao carregar imagem: {str(e)}</i>", self.styles['Normal']))
            
            story.append(PageBreak())

        try:
            doc.build(story)
            return True
        except Exception as e:
            print(f"Erro ao construir PDF: {e}")
            return False

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DocuMaster - Documentador de Impressos")
        self.geometry("1100x700")
        
        # Estrutura de Pastas
        self.data_file = "data.json"
        self.img_folder = "images_storage"
        if not os.path.exists(self.img_folder):
            os.makedirs(self.img_folder)
            
        self.data = self.load_data()
        self.current_image_path = None
        self.check_vars = {} # Para armazenar estados dos checkboxes

        self._setup_ui()

    def _setup_ui(self):
        # Layout: Grid 1x2 (Esquerda: Form, Direita: Lista)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === PAINEL ESQUERDO (Formulário) ===
        self.left_frame = ctk.CTkFrame(self, width=350, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_propagate(False)

        ctk.CTkLabel(self.left_frame, text="Novo Impresso", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)

        # Campos
        self.entry_nome = self.create_input("Nome do Impresso (Título):")
        self.entry_categoria = self.create_input("Categoria (ex: Financeiro):")
        self.entry_origem = self.create_input("Origem (Caminho Menu):")
        
        ctk.CTkLabel(self.left_frame, text="Descrição Sucinta:", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        self.txt_desc = ctk.CTkTextbox(self.left_frame, height=100)
        self.txt_desc.pack(fill="x", padx=20, pady=5)

        # Botão Imagem
        self.btn_img = ctk.CTkButton(self.left_frame, text="Anexar Print (Imagem)", command=self.select_image, fg_color="#eb9e34", hover_color="#cf8b2d")
        self.btn_img.pack(fill="x", padx=20, pady=20)
        self.lbl_img_status = ctk.CTkLabel(self.left_frame, text="Nenhuma imagem", text_color="grey")
        self.lbl_img_status.pack(pady=(0, 10))

        # Botão Salvar
        self.btn_save = ctk.CTkButton(self.left_frame, text="Adicionar à Lista", command=self.add_item, height=40)
        self.btn_save.pack(fill="x", padx=20, pady=10)

        # === PAINEL DIREITO (Lista e Ações) ===
        self.right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Top Bar Direita
        self.top_bar = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        # --- CORREÇÃO AQUI: Troquei mb=10 por pady=(0, 10) ---
        self.top_bar.pack(fill="x", pady=(0, 10)) 
        
        ctk.CTkLabel(self.top_bar, text="Itens Documentados", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        
        self.btn_gen_pdf = ctk.CTkButton(self.top_bar, text="Gerar PDF (Selecionados)", command=self.generate_pdf, fg_color="#2cc985", hover_color="#229c67")
        self.btn_gen_pdf.pack(side="right")

        # Lista Scrollavel
        self.scroll_frame = ctk.CTkScrollableFrame(self.right_frame, label_text="Selecione para incluir no PDF")
        self.scroll_frame.pack(fill="both", expand=True)

        self.refresh_list()

    def create_input(self, label):
        ctk.CTkLabel(self.left_frame, text=label, anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry = ctk.CTkEntry(self.left_frame)
        entry.pack(fill="x", padx=20, pady=5)
        return entry

    def select_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Imagens", "*.png;*.jpg;*.jpeg;*.bmp")])
        if file_path:
            self.current_image_path = file_path
            self.lbl_img_status.configure(text=os.path.basename(file_path), text_color="white")

    def add_item(self):
        nome = self.entry_nome.get()
        if not nome:
            messagebox.showwarning("Aviso", "O nome do impresso é obrigatório.")
            return

        # Copiar imagem para pasta do projeto
        final_img_path = ""
        if self.current_image_path:
            ext = os.path.splitext(self.current_image_path)[1]
            filename = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            final_img_path = os.path.join(self.img_folder, filename)
            try:
                shutil.copy(self.current_image_path, final_img_path)
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao copiar imagem: {e}")
                return

        new_item = {
            "id": datetime.now().strftime('%Y%m%d%H%M%S'),
            "nome": nome,
            "categoria": self.entry_categoria.get(),
            "origem": self.entry_origem.get(),
            "descricao": self.txt_desc.get("1.0", "end-1c"),
            "image_path": final_img_path,
            "selected": True # Default
        }

        self.data.append(new_item)
        self.save_data()
        self.clear_form()
        self.refresh_list()

    def clear_form(self):
        self.entry_nome.delete(0, "end")
        self.entry_categoria.delete(0, "end")
        self.entry_origem.delete(0, "end")
        self.txt_desc.delete("1.0", "end")
        self.current_image_path = None
        self.lbl_img_status.configure(text="Nenhuma imagem", text_color="grey")

    def refresh_list(self):
        # Limpa widgets anteriores
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        self.check_vars = {}

        for item in reversed(self.data): # Mais recentes primeiro
            row = ctk.CTkFrame(self.scroll_frame)
            row.pack(fill="x", pady=5, padx=5)

            # Checkbox de seleção
            var = ctk.BooleanVar(value=True)
            self.check_vars[item['id']] = var
            chk = ctk.CTkCheckBox(row, text="", variable=var, width=20)
            chk.pack(side="left", padx=10)

            # Informações
            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            
            ctk.CTkLabel(info_frame, text=item['nome'], font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(info_frame, text=f"{item['categoria']} | {item['origem']}", text_color="grey", anchor="w").pack(fill="x")

            # Botão Excluir
            ctk.CTkButton(row, text="Excluir", width=60, fg_color="#c92c2c", hover_color="#9c2222",
                          command=lambda i=item: self.delete_item(i)).pack(side="right", padx=10)

    def delete_item(self, item):
        if messagebox.askyesno("Confirmar", f"Excluir '{item['nome']}'?"):
            self.data.remove(item)
            # Opcional: deletar imagem física também
            if item['image_path'] and os.path.exists(item['image_path']):
                try: os.remove(item['image_path'])
                except: pass
            
            self.save_data()
            self.refresh_list()

    def generate_pdf(self):
        # Filtrar apenas os selecionados
        selected_items = [item for item in self.data if item['id'] in self.check_vars and self.check_vars[item['id']].get()]
        
        if not selected_items:
            messagebox.showwarning("Aviso", "Selecione pelo menos um item para gerar o PDF.")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialfile="Catalogo_Impressos.pdf")
        if save_path:
            pdf_gen = ReportPDFGenerator(save_path)
            success = pdf_gen.generate(selected_items)
            if success:
                messagebox.showinfo("Sucesso", "PDF gerado com sucesso!")
                try:
                    os.startfile(save_path) # Abre o PDF automaticamente (Windows)
                except:
                    pass
            else:
                messagebox.showerror("Erro", "Falha ao gerar PDF. Verifique se o arquivo não está aberto.")

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    app = App()
    app.mainloop()