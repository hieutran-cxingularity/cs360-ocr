from fastapi import FastAPI,Response
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from openai.types.chat import ChatCompletion
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from elasticsearch import Elasticsearch
ELASTIC_CLOUD_ID="cs360:dXMtY2VudHJhbDEuZ2NwLmNsb3VkLmVzLmlvOjQ0MyRiZTBiZGVjMGNmOGE0NTZiYTBkNDZiZDRmMjcyODg5NCQzYTI1ZmQ2OWYyMTA0ZjUwYjBiYWQyN2EzNzk2ZmE3Zg=="
# Create the client instance
elasticsearch_client = Elasticsearch(
    cloud_id=ELASTIC_CLOUD_ID,
    basic_auth=('elastic', '8Y6gBmZRXS4er9gZvnfnLHB1')
)
import json
from pydantic import BaseModel
# from wand.image import Image as wi
import io
# init config
import os
import boto3
from wand.image import Image as wimage
app = FastAPI()
class OCRData(BaseModel):
  ocr: str
  feature_extraction: str
  scoring: str
  customer_id: int
  document_key: str
  version_doc: str
class OCRRequest(BaseModel):
  customer_id: int
  document_key: str
  version_doc: str
origins = ["*"]
client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key="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",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get('/healthcheck')
async def heathcheck():
    return 'ok'
@app.post('/list-documents')
async def list_documents(customer_id: int):
  client_aws = boto3.client("s3",
          aws_access_key_id='AKIAVVEDCGQLGGFPWE5T',
          aws_secret_access_key='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',
          region_name='ap-southeast-1'
        )
  result =[]
  list = client_aws.list_objects(Bucket='cs360-customer-document', Prefix='%s/'%(customer_id))['Contents']
  for i in list:
    versions = []
    for j in client_aws.list_object_versions(Bucket='cs360-customer-document', Prefix=i['Key'])['Versions']:
      versions.append(j['VersionId'])
    i['versions'] = versions
  return {'result': list}

@app.get('/document-content')
async def document_content(customer_id: int, document_name: str, version: str):
  aws_client = boto3.client("s3", 
          aws_access_key_id='AKIAVVEDCGQLGGFPWE5T',
          aws_secret_access_key='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',
          region_name='ap-southeast-1'  
        )
  headers = {'Content-Disposition': 'inline; filename="out.pdf"'}

  data = aws_client.get_object(Bucket='cs360-customer-document', Key='%s/%s'%(customer_id, document_name), VersionId=version)
  choosen_file = data['Body'].read()
  buffer = io.BytesIO(choosen_file)
  
  return Response(buffer.getvalue(), headers=headers, media_type='application/pdf')
@app.post("/get-ocr-result")
async def get_ocr(request: OCRRequest):
  query = {  
    'bool':{
      "must":[
        {'match': {            
            'document_key': request.document_key
        }},
        {'match': {
            'customer_id': request.customer_id
        }},
        {'match': {
            'version_doc': request.version_doc
        }}
      ]
    }
  }
  resp = elasticsearch_client.search(index="customer-document", query=query)
  return {"result": resp['hits']['hits']}

@app.post("/store-ocr-result")
async def store_ocr(request: OCRData):
  query = {  
    'bool':{
      "must":[
        {'match': {            
            'document_key': request.document_key
        }},
        {'match': {            
            'customer_id': request.customer_id
        }},
        {'match': {            
            'version_doc': request.version_doc
        }}
      ]
    }             
  }
  resp = elasticsearch_client.search(index="customer-document", query=query)
  if len(resp['hits']['hits']) == 0:
      elasticsearch_client.index(
      index='customer-document',
      document={
        'ocr': request.ocr,
        'customer_id': request.customer_id,
        'feature_extraction': request.feature_extraction,
        'scoring': request.scoring,
        'document_key': request.document_key,
        'version_doc': request.version_doc
      }
    )
  else:
    elasticsearch_client.update(index="customer-document", id=resp['hits']['hits'][0]['_id'], doc={
      "ocr": request.ocr,
      "feature_extraction": request.feature_extraction,
      "scoring": request.scoring
    })
  return {"result":True}
@app.post("/ocr1")
async def ocr_func(document_name: str, version: str, customer_id: int):
  client_aws = boto3.client("s3",
          aws_access_key_id='AKIAVVEDCGQLGGFPWE5T',
          aws_secret_access_key='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',
          region_name='ap-southeast-1'
        )
  choosen_file = None
  data = client_aws.get_object(Bucket='cs360-customer-document', Key=document_name, VersionId=version)
  choosen_file = data['Body'].read()
  query = {
    'bool':{
      "must":[
        {'match': {
            'document_key': document_name
        }},
        {'match': {
            'customer_id': customer_id
        }},
        {'match': {
            'version_doc': version
        }}
      ]
    }
  }
  resp = elasticsearch_client.search(index="customer-document", query=query)
  combined_text=''
  if len(resp['hits']['hits']) == 0:
    page_images=[]
    with wimage(blob=choosen_file, resolution=200) as img:
      for page_wand_image_seq in img.sequence:
        page_wand_image = wimage(image=page_wand_image_seq)
        # page_wand_image.save(filename=str(i)+".jpg")
        # i+=1
        page_jpeg_bytes = page_wand_image.make_blob(format="jpeg")
        page_jpeg_data = io.BytesIO(page_jpeg_bytes)
        page_image = Image.open(page_jpeg_data)
        text = pytesseract.image_to_string(page_image)
        # Append the extracted text
        combined_text += text + "\n"
        page_images.append(page_image)
      elasticsearch_client.index(
        index='customer-document',
        document={
           'customer_id': customer_id,
           'document_key': document_name,
           'version_doc': version,
           'combined_text': combined_text
      })

  else:
    combined_text=resp['hits']['hits'][0]['_source']['combined_text']
  return {"combined_text": combined_text}

@app.post("/ocr2")
async def ocr_func1(document_name: str, version: str, customer_id: int, recalculate: bool):
  query = {
    'bool':{
      "must":[
        {'match': {
            'document_key': document_name
        }},
        {'match': {
            'customer_id': customer_id
        }},
        {'match': {
            'version_doc': version
        }}
      ]
    }
  }
  resp = elasticsearch_client.search(index="customer-document", query=query)
  combined_text=resp['hits']['hits'][0]['_source']['combined_text']
  response = resp['hits']['hits'][0]['_source'].get('response')
  response1 = None
  if response is None or recalculate == True:
    response1 = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "You are a Financial auditor who reviews a unstructured financial statement into JSON document."},
            {"role": "user", "content": f"convert financial statements into comprehensive balancesheet into JSON format {combined_text} in ENGLISH!!. Name, Year, Current Assets, Current Liabilities, Total Liabilities, Equity, Debt-to-Equity Ratio, Interest Coverage Ratio, Inventory, Accounts Receivable, Cash and Cash Equivalents, Retained Earnings, Fixed Assets, Long-term Debt, Accounts Payable, Prepaid Expenses, Accrued Liabilities, Deferred Tax Liabilities, Intangible Assets, Shareholder's Equity, Goodwill, Other Long-term Assets."}
        ]
    )
    elasticsearch_client.update(index="customer-document", id=resp['hits']['hits'][0]['_id'], doc={
      "response": json.dumps(response1.dict())
    })
    return {"step1": response1.choices[0].message.content}
  elif response is not None:
    old_res = ChatCompletion(**json.loads(response))
    return {"step1": old_res.choices[0].message.content}

@app.post("/ocr3")
async def ocr_func2(document_name: str, version: str, customer_id: int, recalculate: bool):
  query = {
    'bool':{
      "must":[
        {'match': {
            'document_key': document_name
        }},
        {'match': {
            'customer_id': customer_id
        }},
        {'match': {
            'version_doc': version
        }}
      ]
    }
  }
  resp = elasticsearch_client.search(index="customer-document", query=query)
  combined_text=resp['hits']['hits'][0]['_source']['combined_text']
  old_response2 = resp['hits']['hits'][0]['_source'].get('response2')
  if old_response2 is None or recalculate == True:
    response2 = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "You are a Financial auditor who reviews a unstructured financial statement into JSON document. return only JSON file, no comments, no dotted data like so on.. or similar data. be to the point"},
            {"role": "user", "content": f"convert financial statements into comprehensive income statement PnL into JSON format {combined_text}in ENGLISH!!. Name, Year, Revenue, Cost of Goods Sold, Gross Profit, Operating Expenses, Operating Income, Interest Expense, Depreciation and Amortization, Earnings Before Interest and Taxes (EBIT), Net Income, Sales & Marketing Expenses, Administrative Expenses, Research and Development Expenses, Other Operating Expenses, Earnings Before Interest, Taxes, Depreciation, and Amortization (EBITDA), Tax Expense, Net Profit Margin, Gross Margin, Other Income, Other Expenses, Dividend Income."}
        ]
  )
    elasticsearch_client.update(index="customer-document", id=resp['hits']['hits'][0]['_id'], doc={
      "response2": json.dumps(response2.dict()),
      "ocr": response2.choices[0].message.content
    })
    return {"ocr": response2.choices[0].message.content}
  elif old_response2 is not None:
    old_res = ChatCompletion(**json.loads(old_response2))
    return {"ocr": old_res.choices[0].message.content}
@app.post("/ocr4")
async def ocr_func3(document_name: str, version: str, customer_id: int, recalculate: bool):
  query = {
    'bool':{
      "must":[
        {'match': {
            'document_key': document_name
        }},
        {'match': {
            'customer_id': customer_id
        }},
        {'match': {
            'version_doc': version
        }}
      ]
    }
  }
  resp = elasticsearch_client.search(index="customer-document", query=query)
  response2 = resp['hits']['hits'][0]['_source'].get('response2')
  response = resp['hits']['hits'][0]['_source'].get('response')
  old_response3 = resp['hits']['hits'][0]['_source'].get('response3')
  if old_response3 is None or recalculate == True:
    response3 = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "You are a Financial auditor who reviews a unstructured financial statement into JSON document. return only JSON file, no comments, no dotted data like so on.. or similar data. be to the point. and derive and calculate necessary data from statements"},
            {"role": "user", "content": f" based on following financial statemnt {response}{response2}. derive and calculate exactly all the following factors  in JSON format Debt-to-Equity Ratio, Interest Coverage Ratio, Current Ratio, Quick Ratio, Return on Assets (ROA), Return on Equity (ROE), Net Profit Margin, Gross Margin, Asset Turnover Ratio, Inventory Turnover Ratio, Accounts Receivable Turnover Ratio, Debt Service Coverage Ratio (DSCR), Fixed Asset Turnover Ratio, EBITDA Margin, Working Capital."}
        ]
    )
    elasticsearch_client.update(index="customer-document", id=resp['hits']['hits'][0]['_id'], doc={
      "response3": json.dumps(response3.dict()),
      "feature_extraction": response3.choices[0].message.content
    })

    return {"feature_extraction": response3.choices[0].message.content}
  elif old_response3 is not None:
    old_res = ChatCompletion(**json.loads(old_response3))
    return {"feature_extraction": old_res.choices[0].message.content}

@app.post("/ocr5")
async def ocr_func4(document_name: str, version: str, customer_id: int, recalculate: bool):
  query = {
    'bool':{
      "must":[
        {'match': {
            'document_key': document_name
        }},
        {'match': {
            'customer_id': customer_id
        }},
        {'match': {
            'version_doc': version
        }}
      ]
    }
  }
  resp = elasticsearch_client.search(index="customer-document", query=query)
  response3 = resp['hits']['hits'][0]['_source'].get('response3')
  old_response4 = resp['hits']['hits'][0]['_source'].get('response4')
  if old_response4 is None or recalculate == True:
    response4 = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
        {"role": "system", "content": "You are a Financial auditor who reviews a unstructured financial statement into JSON document. return only JSON file, no comments, no dotted data like so on.. or similar data. be to the point. and derive and calculate necessary data from statements"},
            {"role": "user", "content": f" based on following financial statemnt {response3}. credit score from 1 to 5, 5 being healtiest and highlight top 4 some vulnerbilities and top 4 strengths in few words, results should have credit_score, top_vunerbilities, top_strengths in JSON format. dont need any other infomation"}
      ]
    )    
    elasticsearch_client.update(index="customer-document", id=resp['hits']['hits'][0]['_id'], doc={
      "response4": json.dumps(response4.dict()),
      "scoring": response4.choices[0].message.content
    })
    return {
      "scoring": response4.choices[0].message.content
    }
  elif old_response4 is not None:
    old_res = ChatCompletion(**json.loads(old_response4))
    return {"scoring": old_res.choices[0].message.content}

