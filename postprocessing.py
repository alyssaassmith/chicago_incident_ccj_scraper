import datetime
import pandas as pd
import numpy as np
import geopandas as gpd
from azure.storage.blob import BlobServiceClient, ContainerClient
from io import BytesIO
import os

API_KEY = os.environ['AZURE_BLOB']

def azure_upload_df(container, df, filename, con, filepath=None ):
    
    """
    Upload DataFrame to Azure Blob Storage for given container
    Keyword arguments:
    container -- the container folder name 
    df -- the dataframe(df) object
    filename -- name of the file
    filepath -- the filename to use for the blob 
    con -- azure connection string
    """
    
    if filepath != None:
        blob_path = filepath + filename
    else:
        blob_path = filename
        
    # initialize client
    blob_service_client = BlobServiceClient(account_url=con)
    
    #specify file path
    blob_client = blob_service_client.get_blob_client(
    container=container, blob=blob_path
        )
    
    #convert dataframe to a string object
    output = df.to_csv(index=False, encoding="utf-8")
    
    #upload file
    # overwrite the data
    blob_client.upload_blob(data=output, blob_type="BlockBlob", overwrite=True)
    
    #close the client; we're done with it!
    blob_service_client.close()

def inc_data_read(start_year = 2018, full_dataset = True, convert_cook_crs = True):
    
    """
    Pulling in City of Chicago Incident data; returns pandas dataframe of incidents.
    start_year: input starting year for requested data
    full_dataset: choose to pull in full dataset or small subset of data
    convert_cook_crs: choose to convert to local espg to match beat data or not 
    """

    

    if full_dataset == True:
        print("Pulling full dataset")
        limit = 20000000
    else:
        print("Small subset")
        limit = 200
    
    today = datetime.date.today()
    
    current_yr = today.year
    inc_df_list = []
    
    for year in range(start_year, current_yr + 1):

        print(year)
        
        inc_data_yr = pd.read_csv(
            f'https://data.cityofchicago.org/resource/ijzp-q8t2.csv?$limit={limit}&$where=date%20between%20%27{year}-01-01T00:00:00%27%20and%20%27{year}-12-31T23:59:59%27', storage_options={'verify': False}
        )
        inc_df_list.append(inc_data_yr)
        
    inc_df = pd.concat(inc_df_list, ignore_index=True)

    geometry = gpd.points_from_xy(inc_df.longitude, inc_df.latitude, crs="EPSG:4326")
    inc_gdf = gpd.GeoDataFrame(
    inc_df, geometry=geometry 
     )     



    if convert_cook_crs == True: 
        inc_gdf = inc_gdf.to_crs(epsg=26916) 
        
  
        print(inc_gdf.crs)
        print(inc_gdf.shape)

        return inc_gdf


df = inc_data_read(start_year = 2018, full_dataset = True, convert_cook_crs = True)

df.head()

df['date'] = df['date'].astype(str)

df['inc_data_read'] = pd.to_datetime(df['date'], errors='coerce')

df['date'] = pd.to_datetime(df['date'])

print(df['date'].head())

print(df['date'].dtype)

print(df['date'].unique())

df['year'].unique()

df['MONTH'] = df['date'].dt.month
df['DAY'] = df['date'].dt.day
df['YEAR'] = df['date'].dt.year

df.columns

df = df[df['inc_data_read'] >= '2018-01-01']

lookup_path = "data/cpd_offense_lookup.csv"
lookup = pd.read_csv(lookup_path, )

df['iucr'] = df['iucr'].str.replace(r'\D', '', regex=True)
df['iucr'] = pd.to_numeric(df['iucr'], errors='coerce').fillna(0).astype(int)
lookup['IUCR'] =  pd.to_numeric(lookup['IUCR'], errors='coerce').fillna(0).astype(int)

df = df.merge(lookup, left_on='iucr',right_on='IUCR', how='left')

print(lookup.dtypes)

df['DomesticSort'] = np.where(df['domestic'] == True, 1,
    np.where(df['domestic'] == False, 0, np.nan))
df['Domestic'] = df['domestic'].map({True: 'DV Incident', False: 'Non-DV Incident'})

domestic_keywords = ['Domestic Battery', 'Aggravated Domestic Battery']
df.loc[df['OffenseDescription'].isin(domestic_keywords), 'DomesticSort'] = 1
df.loc[df['OffenseDescription'].isin(domestic_keywords), 'Domestic'] = 'DV Incident'

df['ArrestSort'] = df['arrest'].map({True: 1, False: 0})
df['Arrest'] = df['arrest'].map({True: 'arrest', False: 'No arrest'})

def assign_police_district(beat):
    if beat in [111,112,113,114,121,122,123,124,131,132,133]: return 1
    elif beat in [211,212,213,214,215,221,222,223,224,225,231,232,233,234,235]: return 2
    elif 311 <= beat <= 334: return 3
    elif 411 <= beat <= 434: return 4
    elif 511 <= beat <= 533: return 5
    elif 611 <= beat <= 634: return 6
    elif 711 <= beat <= 735: return 7
    elif 811 <= beat <= 835: return 8
    elif 911 <= beat <= 935: return 9
    elif 1011 <= beat <= 1034: return 10
    elif 1111 <= beat <= 1135: return 11
    elif 1211 <= beat <= 1235: return 12
    elif 1411 <= beat <= 1434: return 14
    elif 1511 <= beat <= 1533: return 15
    elif 1611 <= beat <= 1655: return 16
    elif 1711 <= beat <= 1733: return 17
    elif 1811 <= beat <= 1834: return 18
    elif 1911 <= beat <= 1935: return 19
    elif 2011 <= beat <= 2033: return 20
    elif 2211 <= beat <= 2234: return 22
    elif 2411 <= beat <= 2433: return 24
    elif 2511 <= beat <= 2535: return 25
    return np.nan


df['PoliceDistrict'] = df['beat'].apply(lambda x: assign_police_district(int(x)) if pd.notnull(x) else np.nan)

df['CaseSort'] = 1
df['Case'] = 'All Incidents'

print(df['date'].max())


drop_cols = [
    'id', 'case_number', 'date', 'block', 'primary_type', 'description', 'location_description', 'fbi_code',
    'x_coordinate', 'y_coordinate', 'updated_on', 'latitude', 'longitude', 'location', 'MONTH', 'DAY', 'arrest', 'iucr', 'domestic', 'year'
]
df.drop(columns=drop_cols, inplace=True)

col_rename = {'district':'District','ward':'Ward','community_area':'CommunityArea'}
df = df.rename(col_rename,axis=1)

print(df.columns)
print(df.isnull().sum())
output_csv = "incident.csv"
#df.to_csv(output_csv, index=False, encoding='utf-8')

azure_upload_df(container='data', df=df, filepath='/',\
                filename= output_csv, con=API_KEY)






