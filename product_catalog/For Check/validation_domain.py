"""Source schemas and exact comparison values for PO/POP validation."""
import re

VERSION = '1.2.0'
RULE_NUMBERS = tuple(range(1, 16))
UNIT = 'unit_name-mh_mg00562'
MODEL = 'model-mh_mg00556'
MAIN = 'main_model-mh_mg00554'
TYPE = 'product_type-mh_mg00162'
BLANK = (None, '')

SCHEMAS = {
 'pv': ('Product Offer Price', ['Product Offer Price ID', 'priceType', 'price_value'], ['pid', 'price_type', 'price_value']),
 'pt': ('Product Offer Price', ['Product Offer Price ID', 'priceType'], ['pid', 'price_type']),
 'ch': ('Channel', ['POP_ID', 'ProductOfferPrice.Channel'], ['pid', 'channel']),
 'po': ('ProductOffer', ['Product Id'], ['po']),
 'm': ('Product Offer Price', ['Product Offer Price ID'], ['pid']),
 'o': ('Product Offer Price', ['Product Offer ID','Product Offer Price ID'], ['po','pid']),
 'v': ('Product_Variants', ['Product Variants.Product Id','Product Variants.variantId','Product Variants.specCharacteristics','Product Variants.value','Product Variants.sku'], ['po','vid','cids','vals','sku']),
 'l': ('Variant_ProductOffering_Price', ['variantProductOfferingPrice.variantId','variantProductOfferingPrice.productOfferingPrice'], ['vid','pid']),
 'c': ('Characteristics for Price', ['Product Offer Price ID','Characteristics ID','Char Name','value'], ['pid','cid','name','val']),
 't': ('POP_metaExt_productInfo', ['Product Offer Price ID','matCode','commercialName','sapDescriptionEng','sapDescriptionTha'], ['pid','sku','commercial_name','sap_eng','sap_tha']),
 'cv': ('Char_Value', ['Char Value.Product Offer ID','Char Value.Product Offer Characteristics ID','Char Value.Product Offer Characteristics Name','Char Value.value','Char Value.Product Spec ID','Char Value.Product Spec Name','Char Value.valueType','Char Value.isDefault'], ['po','cid','name','val','spec_id','spec_name','value_type','is_default']),
}

CV_DUPLICATE_KEY = ('po', 'cid', 'name', 'value_type', 'val')
RULE_INPUTS = {
    1: {'m','t'}, 2: {'v','l','t'}, 3: {'t','l','v'}, 4: {'c'},
    5: {'m','c'}, 6: {'m','c','l','v'}, 7: {'m','c','l','v','cv'}, 8: {'m','o','c','cv'},
    9: {'po','m','o','v','l','c','cv'}, 10: {'cv'}, 11: {'v','l','pt','ch'},
    12: {'cv'}, 13: {'t'}, 14: {'v','l','pv','c'}, 15: {'v'},
}
PRODUCT_CHAR_COLUMNS = ('MAIN_MODEL', 'BRAND', 'COMPANY', 'COLOR', 'CAPACITY', 'PRODUCT_TYPE',
                        'PRODUCT_SUBTYPE', 'MAT_TYPE', 'MODEL', 'UNIT_NAME')


def char_key(name):
    return name.split('-mh_mg', 1)[0].replace('_', '').lower()

CV_DETAIL_FIELDS = ('po', 'spec_id', 'spec_name', 'cid', 'name', 'value_type', 'val', 'is_default')
CV_DETAIL_HEADERS = [SCHEMAS['cv'][1][SCHEMAS['cv'][2].index(field)] for field in CV_DETAIL_FIELDS]


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


