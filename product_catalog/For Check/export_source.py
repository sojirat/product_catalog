"""Resolve the split XLSX files produced by export_template_mapping.py."""
from datetime import datetime
from pathlib import Path

DEFAULT_EXPORT_DIR = Path(__file__).resolve().parents[2] / 'export'


def resolve_export_input(value=None):
    """Accept an export round name, a round path, or an XLSX directory."""
    if value is None:
        return latest_export_input(DEFAULT_EXPORT_DIR)
    value = Path(value)
    root = DEFAULT_EXPORT_DIR / value if not value.is_absolute() and len(value.parts) == 1 else value
    if (root / 'xlsx').is_dir():
        root = root / 'xlsx'
    if not root.is_dir():
        raise NotADirectoryError(root)
    return root.resolve()


# Table key: export subfolder, file prefix, raw workbook sheet name.
EXPORT_FILES = {
    'po': ('Product Offer', 'ProductOffer_', 'ProductOffer'),
    'o': ('Product Offer', 'product_offer_price_', 'Product Offer Price'),
    'v': ('Product Offer', 'PO_Product_Variants_', 'Product Variants'),
    'l': ('Product Offer', 'Variant_ProductOffering_Price_', 'variantProductOfferingPrice'),
    'm': ('Product Offer Price', 'productOfferPrice_', 'Product Offer Price'),
    'c': ('Product Offer Price', 'CharacteristicsForPrice_', 'Characteristics for Price'),
    't': ('MetaExtension POP', 'POP_metaExt_productInfo_', 'metaExtension POP'),
}


def latest_export_input(export_dir):
    """Select the newest export by its DDMMYYYYHHMMSS folder name."""
    candidates = []
    for folder in export_dir.iterdir():
        if not folder.is_dir() or len(folder.name) != 14 or not folder.name.isascii() or not folder.name.isdigit():
            continue
        try:
            timestamp = datetime.strptime(folder.name, '%d%m%Y%H%M%S')
        except ValueError:
            continue
        candidates.append((timestamp, folder))
    if not candidates:
        raise ValueError(f'No timestamped export folders (DDMMYYYYHHMMSS) found in {export_dir}')
    root = max(candidates)[1] / 'xlsx'
    if not root.is_dir():
        raise NotADirectoryError(f'Latest export has no xlsx folder: {root}')
    return root.resolve()


def one_file(folder, pattern):
    candidates = sorted(folder.glob(pattern))
    if len(candidates) != 1:
        raise ValueError(f'Expected exactly one {folder / pattern}; found {len(candidates)}')
    return candidates[0].resolve()


def discover_export_inputs(input_dir, char_values=None):
    root = input_dir.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    sources = {table: one_file(root / folder, prefix + '*.xlsx')
               for table, (folder, prefix, _) in EXPORT_FILES.items()}
    if char_values:
        cv_paths = [path.resolve() for path in char_values]
    else:
        cv_xlsx = sorted((root / 'Product Offer').glob('PO_Char_Value_*.xlsx'))
        if cv_xlsx:
            cv_paths = [one_file(root / 'Product Offer', 'PO_Char_Value_*.xlsx')]
        else:
            # Large Char_Value datasets are omitted from XLSX by the exporter.
            cv_paths = [one_file(root.parent / 'csv' / 'Product Offer', 'PO_Char_Value_*.csv')]
    for path in cv_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix.lower() not in ('.xlsx', '.csv', '.zip'):
            raise ValueError(f'Unsupported Char_Value file: {path}')
    if any(path.suffix.lower() == '.xlsx' for path in cv_paths) and len(cv_paths) != 1:
        raise ValueError('Char_Value XLSX must be a single file')
    return sources, cv_paths


def read_export_inputs(validator, sources, cv_paths, env_path=None, on_source=None):
    from csv_fallback import read_with_fallback
    env_path = env_path or Path(__file__).resolve().parent.parent / '.env'
    for table, path in sources.items():
        read_with_fallback(validator,path,table,EXPORT_FILES[table][2],env_path,on_source=on_source)
    if cv_paths[0].suffix.lower() == '.xlsx':
        read_with_fallback(validator,cv_paths[0],'cv','Char_Value',env_path,on_source=on_source)
    else:
        validator.read_cv_files(cv_paths)
