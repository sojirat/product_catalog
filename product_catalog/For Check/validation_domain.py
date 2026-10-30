"""Source schemas and exact comparison values for PO/POP validation."""
import re

VERSION = '1.1.0'
UNIT = 'unit_name-mh_mg00562'
MODEL = 'model-mh_mg00556'
MAIN = 'main_model-mh_mg00554'
TYPE = 'product_type-mh_mg00162'
BLANK = (None, '')

SCHEMAS = {
 'po': ('ProductOffer', ['Product Id'], ['po']),
 'm': ('Product Offer Price', ['Product Offer Price ID'], ['pid']),
 'o': ('Product Offer Price', ['Product Offer ID','Product Offer Price ID'], ['po','pid']),
 'v': ('Product_Variants', ['Product Variants.Product Id','Product Variants.variantId','Product Variants.specCharacteristics','Product Variants.value','Product Variants.sku'], ['po','vid','cids','vals','sku']),
 'l': ('Variant_ProductOffering_Price', ['variantProductOfferingPrice.variantId','variantProductOfferingPrice.productOfferingPrice'], ['vid','pid']),
 'c': ('Characteristics for Price', ['Product Offer Price ID','Characteristics ID','Char Name','value'], ['pid','cid','name','val']),
 't': ('POP_metaExt_productInfo', ['Product Offer Price ID','matCode'], ['pid','sku']),
 'cv': ('Char_Value', ['Char Value.Product Offer ID','Char Value.Product Offer Characteristics ID','Char Value.Product Offer Characteristics Name','Char Value.value'], ['po','cid','name','val']),
}


def parse_pairs(ids: str, vals: str):
 """Comma lists, NOT CSV syntax: preserve order/empty members/literal quotes.

 Embedded quotes e.g. PRO9.7"256GB are literal data. A quoted token containing
 a comma is ambiguous because an inner CSV grammar was never specified.
 """
 if ids == vals == '':
  return [], 'BOTH_EMPTY'
 if re.search(r'(^|,)"[^"\r\n]*,[^"\r\n]*"(?=,|$)', ids) or re.search(r'(^|,)"[^"\r\n]*,[^"\r\n]*"(?=,|$)', vals):
  return [], 'AMBIGUOUS_QUOTES'
 a, b = ids.split(','), vals.split(',')
 if len(a) != len(b):
  return [], 'LENGTH_MISMATCH'
 if '' in a or '' in b:
  return [], 'EMPTY_MEMBER'
 return list(zip(a, b)), None


