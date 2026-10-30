# Flipkart Invoice & Shipping Label Splitter

## Windows EXE via GitHub Actions (no Python installation on your PC)

This project is configured to build a standalone Windows `.exe` on a Windows cloud runner.

1. Sign in to GitHub and create a **private** repository.
2. Upload the contents of this ZIP to the repository (make sure `.github/workflows/build-windows.yml` is included).
3. Name the default branch `main`.
4. Open the repository's **Actions** tab and enable workflows if GitHub asks.
5. The workflow starts automatically after the first push. Alternatively, open **Build Windows EXE** and select **Run workflow**.
6. When the run is green, open that run, scroll to **Artifacts**, and download `Flipkart_Splitter_Windows_EXE`.
7. Extract the artifact ZIP. It contains `Flipkart_Splitter.exe`.

The EXE is built by GitHub on Windows; this Linux environment does not compile the Windows binary itself.

## Label paper size
Every output shipping label is created on an exact **4 x 6 inch** PDF page (288 x 432 points).
The label artwork is cropped from the Flipkart page and scaled proportionally to fit the 4x6 page; it is not stretched. Depending on source artwork proportions, small white margins may remain.

## Use
1. Open `Flipkart_Splitter.exe`.
2. Add PDF files or a folder.
3. Choose an output folder.
4. Click **SPLIT LABELS & INVOICES**.
5. The app creates `Labels` and `Invoices` folders.

## Supported inputs
- Combined Flipkart pages with label above invoice.
- Separate label-only PDF pages.
- Separate invoice-only PDF pages.
- Multiple files and multi-page PDFs.

## Important
- Local processing only; PDFs are not uploaded by the application.
- Original PDFs are not modified.
- Check a sample label in your thermal printer's print preview and set paper size to 4 x 6 inches / 100 x 150 mm, scaling 100% or Actual Size. Printer-driver settings can override PDF page size.
- If Flipkart changes its template, inspect sample output before bulk printing.
