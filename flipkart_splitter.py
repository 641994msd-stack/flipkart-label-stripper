import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import fitz  # PyMuPDF

APP_NAME = "Flipkart Invoice & Label Splitter"

def safe_name(value):
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value or "").strip("_")
    return value[:80] or "document"

def page_text(page):
    try:
        return page.get_text("text")
    except Exception:
        return ""

def order_id(text):
    m = re.search(r"Order\s*Id\s*:\s*([A-Z0-9]+)", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(OD\d{10,})\b", text, re.I)
    return m.group(1) if m else None

def awb_id(text):
    m = re.search(r"AWB\s*No\.?\s*[: ]*\s*([A-Z0-9]+)", text, re.I)
    return m.group(1) if m else None

def add_clipped_page(out_doc, source_page, clip):
    new_page = out_doc.new_page(width=clip.width, height=clip.height)
    new_page.show_pdf_page(new_page.rect, source_page.parent, source_page.number, clip=clip)

def label_content_rect(page, split_y):
    # Use all text blocks above the tear line to estimate the actual label bounds.
    blocks = page.get_text("blocks")
    boxes = []
    for block in blocks:
        x0, y0, x1, y1 = block[:4]
        if y0 < split_y and y1 > 18:
            boxes.append(fitz.Rect(x0, y0, x1, min(y1, split_y)))
    if not boxes:
        return fitz.Rect(0, 0, page.rect.width, split_y)
    bounds = boxes[0]
    for box in boxes[1:]:
        bounds |= box
    # Include barcode/QR and border artwork around the text.
    bounds.x0 = max(0, bounds.x0 - 18)
    bounds.x1 = min(page.rect.width, bounds.x1 + 18)
    bounds.y0 = max(0, bounds.y0 - 12)
    bounds.y1 = min(split_y, bounds.y1 + 12)
    return bounds

def add_label_4x6(out_doc, source_page, clip):
    # Exact 4 x 6 inch media size = 288 x 432 PDF points.
    target_w, target_h = 4 * 72, 6 * 72
    target = out_doc.new_page(width=target_w, height=target_h)
    scale = min(target_w / clip.width, target_h / clip.height)
    draw_w, draw_h = clip.width * scale, clip.height * scale
    x0 = (target_w - draw_w) / 2
    y0 = (target_h - draw_h) / 2
    dest = fitz.Rect(x0, y0, x0 + draw_w, y0 + draw_h)
    target.show_pdf_page(dest, source_page.parent, source_page.number, clip=clip)

def classify_and_split(pdf_paths, output_dir, progress=None):
    labels_dir = os.path.join(output_dir, "Labels")
    invoices_dir = os.path.join(output_dir, "Invoices")
    os.makedirs(labels_dir, exist_ok=True)
    os.makedirs(invoices_dir, exist_ok=True)

    label_pages, invoice_pages = [], []
    combined_count = label_only_count = invoice_only_count = 0
    errors = []

    for path in pdf_paths:
        try:
            src = fitz.open(path)
            stem = os.path.splitext(os.path.basename(path))[0]
            for idx, page in enumerate(src):
                text = page_text(page)
                has_label = bool(re.search(r"AWB\s*No|Shipping/Customer address|E-Kart Logistics", text, re.I))
                has_invoice = bool(re.search(r"Tax Invoice|Invoice No|TOTAL PRICE", text, re.I))
                oid = order_id(text) or safe_name(stem + f"_page{idx+1}")
                awb = awb_id(text)

                if has_label and has_invoice:
                    # Flipkart combined layout: label occupies the upper section;
                    # invoice begins below the dashed separator. This sample's
                    # separator is around y=380 on an A4 portrait page.
                    split_y = find_split_y(page)
                    label_doc = fitz.open()
                    invoice_doc = fitz.open()
                    label_clip = label_content_rect(page, split_y)
                    add_label_4x6(label_doc, page, label_clip)
                    add_clipped_page(invoice_doc, page, fitz.Rect(0, split_y, page.rect.width, page.rect.height))
                    label_path = os.path.join(labels_dir, f"{safe_name(oid)}_{safe_name(awb or 'label')}.pdf")
                    invoice_path = os.path.join(invoices_dir, f"{safe_name(oid)}_invoice.pdf")
                    label_doc.save(label_path, garbage=4, deflate=True)
                    invoice_doc.save(invoice_path, garbage=4, deflate=True)
                    label_doc.close(); invoice_doc.close()
                    combined_count += 1
                elif has_label:
                    out = fitz.open()
                    split_y = page.rect.height
                    label_clip = label_content_rect(page, split_y)
                    add_label_4x6(out, page, label_clip)
                    out.save(os.path.join(labels_dir, f"{safe_name(oid)}_{safe_name(awb or 'label')}.pdf"), garbage=4, deflate=True)
                    out.close()
                    label_only_count += 1
                elif has_invoice:
                    out = fitz.open()
                    out.insert_pdf(src, from_page=idx, to_page=idx)
                    out.save(os.path.join(invoices_dir, f"{safe_name(oid)}_invoice.pdf"), garbage=4, deflate=True)
                    out.close()
                    invoice_only_count += 1
            src.close()
        except Exception as exc:
            errors.append(f"{os.path.basename(path)}: {exc}")
        if progress:
            progress(path)

    return combined_count, label_only_count, invoice_only_count, errors

def find_split_y(page):
    # Prefer the horizontal dashed separator detected from page drawing paths.
    # Fall back to the known Flipkart A4 layout proportion if it is not found.
    candidates = []
    try:
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect and rect.width > page.rect.width * 0.65 and rect.height < 3:
                y = (rect.y0 + rect.y1) / 2
                if page.rect.height * 0.30 < y < page.rect.height * 0.60:
                    candidates.append(y)
    except Exception:
        pass
    if candidates:
        return min(candidates)
    # Flipkart sample: dashed tear line falls at approx 45.1% of A4 page.
    return page.rect.height * 0.451

class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("690x500")
        self.root.minsize(620, 440)
        self.files = []
        self.folder = None
        self.output = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Documents", "Flipkart_Output"))
        self._ui()

    def _ui(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_NAME, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Split combined Flipkart PDFs or sort separate label and invoice PDFs.",
                  font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 16))

        row = ttk.Frame(outer); row.pack(fill="x", pady=4)
        ttk.Button(row, text="Add PDF files", command=self.add_files).pack(side="left")
        ttk.Button(row, text="Add folder", command=self.add_folder).pack(side="left", padx=8)
        ttk.Button(row, text="Clear list", command=self.clear).pack(side="left")
        self.file_label = ttk.Label(outer, text="No PDFs selected", wraplength=630)
        self.file_label.pack(anchor="w", pady=(8, 14))

        ttk.Label(outer, text="Output folder", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        outrow = ttk.Frame(outer); outrow.pack(fill="x", pady=(4, 14))
        ttk.Entry(outrow, textvariable=self.output).pack(side="left", fill="x", expand=True)
        ttk.Button(outrow, text="Browse", command=self.choose_output).pack(side="left", padx=(8, 0))

        ttk.Label(outer, text="Processing", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Ready")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(4, 4))
        self.progress = ttk.Progressbar(outer, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 14))

        ttk.Button(outer, text="SPLIT LABELS & INVOICES", command=self.run,
                   style="Accent.TButton").pack(fill="x", ipady=8)
        ttk.Label(outer, text="Files are processed locally. Original PDFs are not modified.",
                  foreground="#555").pack(anchor="w", pady=(14, 0))

    def add_files(self):
        chosen = filedialog.askopenfilenames(title="Select Flipkart PDF files", filetypes=[("PDF files", "*.pdf")])
        self.files.extend([p for p in chosen if p not in self.files])
        self.refresh()

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing PDFs")
        if folder:
            self.folder = folder
            found = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf")]
            self.files.extend([p for p in found if p not in self.files])
            self.refresh()

    def clear(self):
        self.files = []; self.folder = None; self.refresh()

    def refresh(self):
        self.file_label.config(text=f"{len(self.files)} PDF file(s) selected" +
                               (f" • {self.folder}" if self.folder else ""))

    def choose_output(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder: self.output.set(folder)

    def run(self):
        if not self.files:
            messagebox.showwarning("No PDFs", "Add one or more PDF files or a folder first.")
            return
        out = self.output.get().strip()
        if not out:
            messagebox.showwarning("Output folder", "Choose an output folder.")
            return
        self.progress["maximum"] = len(self.files); self.progress["value"] = 0
        self.status.set("Processing PDFs...")
        self.root.update_idletasks()
        def tick(_):
            self.progress["value"] += 1
            self.root.update_idletasks()
        try:
            result = classify_and_split(self.files, out, tick)
            combined, labels, invoices, errors = result
            self.status.set("Completed")
            summary = (f"Completed successfully.\n\nCombined PDFs split: {combined}\n"
                       f"Label-only pages sorted: {labels}\nInvoice-only pages sorted: {invoices}\n\n"
                       f"Output: {out}")
            if errors: summary += "\n\nErrors:\n" + "\n".join(errors)
            messagebox.showinfo("Finished", summary)
        except Exception as exc:
            self.status.set("Error")
            messagebox.showerror("Processing error", str(exc))

if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names(): style.theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()
