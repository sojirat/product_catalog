cd /Users/milk/_AIS/product_catalog2
python3 -m venv .venv
. .venv/bin/activate
python -V
pip install -r requirements.txt

# ##########################

cd /Users/milk/_AIS/product_catalog2

# Use a compatible Python version if available
python3.11 -m venv .venv
# or: python3.12 -m venv .venv
# or: python3 -m venv .venv

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pymysql deep-translator openpyxl

# ##########################
cd /Users/milk/_AIS/product_catalog2
source .venv/bin/activate
python -m pip install -r requirements.txt
FILES="BM_AIS_Product Offer_v1.6.xlsx|BM_AIS_ProductOfferPrice_v1.6.xlsx|BM_AIS_Resource Specification_v1.6.xlsx|BM_AIS_Product Specification_v1.6.xlsx|BM_AIS_MasterCharacteristics_v1.6.xlsx|BM_AIS_ProductOfferCategory_v1.6.xlsx" make export