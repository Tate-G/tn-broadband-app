import pandas as pd
import numpy as np
import streamlit as st
from bokeh.plotting import figure, show
from bokeh.models import GeoJSONDataSource, LinearColorMapper, ColorBar, FixedTicker, HoverTool, NumeralTickFormatter, Title, ColumnDataSource
from bokeh.palettes import brewer, gray, Colorblind
from bokeh.tile_providers import get_provider, STAMEN_TONER_BACKGROUND, STAMEN_TONER_LABELS
from bokeh.layouts import row, column, gridplot
#from PIL import Image

#import dataframe
map_df_full=pd.read_pickle('./map_df_tn.pkl')

county_codes=pd.read_csv('TN_County_Codes.csv')


#####
#App intro and user input setup
#####

st.title('Broadband Expansion for both Revenue and Equality in Tennessee')
st.markdown('Identifying ideal locations for broadband companies to expand their services to simultaneously capture new customers and close racial and ethnic gaps in internet access.')

#define dictionaries to translate between app descriptions of fields and dataframe column names
field_dict={'All Groups':'Pred_New_BB_Households',
            'All Groups Near High Broadband':'Pred_New_BB_HH_Neighbor_High',
            'Underserved Groups':'Pred_New_BB_Underrep_Households',
            'Underserved Near High Broadband':'Pred_New_BB_Underrep_HH_Neighbor_High'}
actual_dict={'Actual Percent Broadband':'Pct_Broadband',
            'Actual Percent White Non-Hispanic':'Pct_White_Non_Hispanic'}
quantity_options=['Actual Percent Broadband','Actual Percent White Non-Hispanic',
                  'Predicted New Customers','Predicted New Annual Revenue']

#allow user to input values in the sidebar, with default values for the first figures displayed when opening the app
county_options=county_codes['County_Name'].tolist() #['All Counties']+county_codes['County_Name'].tolist()
county=st.sidebar.selectbox('Choose county to display:',county_options,
                            index=county_options.index('Davidson County'))
quantity=st.sidebar.selectbox('Choose actual or prediction to display:',quantity_options,
                              index=quantity_options.index('Predicted New Annual Revenue'))
category=st.sidebar.selectbox('Choose target clients for prediction:',
                              ['All Groups','All Groups Near High Broadband',
                               'Underserved Groups','Underserved Near High Broadband'],
                              index=0)
subscription_price=st.sidebar.slider('Adjust monthly broadband subscription price:',min_value=0,max_value=100,value=50)
st.sidebar.markdown('')
st.sidebar.markdown('')
st.sidebar.markdown('')
st.sidebar.subheader('Garrett Tate')
st.sidebar.subheader('garrett.tate@mg.thedataincubator.com')
st.sidebar.subheader('tn-broadband.herokuapp.com')

if county=='All Counties':
    map_df=map_df_full.copy()
else:
    county_code_selected=county_codes.set_index('County_Name').loc[county,'County_Code']
    map_df=map_df_full[map_df_full['COUNTYFP']==county_code_selected].copy()


#####
#Automated formatting
#####

#calculate scaled revenue values
for _,val in field_dict.items():
    map_df[val+'_revenue']=np.round(map_df[val])*subscription_price*12


#define plot characteristics based on the quantity chosen to display
if quantity in actual_dict.keys():
    field=actual_dict[quantity]
    color_scale='RdBu'
    tick_format='0%'
    pad=0
if quantity=='Predicted New Customers':
    field=field_dict[category]
    color_scale='Blues'
    tick_format='0,0'
    pad=2 #remove lower lighter colors
elif quantity=='Predicted New Annual Revenue':
    field=field_dict[category]+'_revenue'
    color_scale='Greens'
    tick_format='$0,0'
    pad=2 #remove lower lighter colors

if quantity in actual_dict.keys():
    tooltips=[(quantity,'@'+field+'{'+tick_format+'}'),]
    title=quantity
    subtitle=''
else:
    tooltips=[('New Customers','@'+field_dict[category]+'{0,0.}'),
             ('New Revenue','@'+field_dict[category]+'_revenue'+'{$0,0.}')]
    title=quantity
    subtitle='Targeting '+category

#automated definition of intervals for the colorbars on the plot
#max(x) for ['Blues'}[x] is 9, select interval intelligently based on this to be 25, 50, 100, etc
interval=5
low=interval*np.floor(np.min(map_df[field])/interval)
high=interval*np.ceil(np.max(map_df[field])/interval)
while (high-low)/interval+pad > 9:
    interval=interval*2
    if interval>10000:
        interval=(interval//10000)*10000
    elif interval>1000:
        interval=(interval//1000)*1000
    high=interval*np.ceil(np.max(map_df[field])/interval)
    low=interval*np.floor(np.min(map_df[field])/interval)

if quantity in actual_dict.keys():
    interval=interval/100
    low=low/100
    high=high/100
for _,val in actual_dict.items():
    map_df[val]=map_df[val]/100
    

#convert the dataframe into a GeoJSON
map_source=GeoJSONDataSource(geojson=map_df.to_json())


#####
#create the plots
#####

st.header(title)
if subtitle != '':
    st.subheader(subtitle)

p=figure(tools='pan,wheel_zoom,reset',height=600,width=700,tooltips=tooltips)
#if subtitle != '':
#    p.add_layout(Title(text=subtitle,text_font_size='18pt'),'above')
#p.add_layout(Title(text=title,text_font_size='24pt'),'above')
p.xgrid.grid_line_color=None
p.ygrid.grid_line_color=None
p.axis.visible=False

p.add_tile(get_provider(STAMEN_TONER_BACKGROUND),alpha=0.5)

bins=max(3,int(np.round((high-low)/interval+pad)))
if high==0:
    l=['#ffffff']*bins  #plot all white if highest value is 0
    palette=l[pad:]
else:
    palette=brewer[color_scale][bins][::-1][pad:]
    if low==0 and quantity not in actual_dict.keys():
        pal=list(palette)
        pal[0]='#f1f1f1'
        palette=tuple(pal)
color_mapper=LinearColorMapper(palette=palette, low=low, high=high, nan_color='white')
color_bar=ColorBar(color_mapper=color_mapper,orientation='horizontal',padding=20,margin=10,
                   ticker=FixedTicker(ticks=np.linspace(low,high,bins-pad+1)),
                   formatter=NumeralTickFormatter(format=tick_format))
               


tracts=p.patches('xs','ys',source=map_source,
                 fill_color={'field':field,'transform':color_mapper},
                 line_color='black',fill_alpha=0.7)

p.add_tile(get_provider(STAMEN_TONER_LABELS),alpha=0.8)
p.add_layout(color_bar,'below')

st.bokeh_chart(p)

#function to create map of a single tract with key info written with it
def tract_info_plot(tract_dataframe,field=field,palette=palette,low=low,high=high,quantity=quantity,field_dict=field_dict):
    tract_df=tract_dataframe.copy()
    tract_source=GeoJSONDataSource(geojson=tract_df.to_json())
    fig_height=500
    fig_width=250
    p2=figure(tools='pan,wheel_zoom,reset',height=fig_height,width=fig_width,tooltips=tooltips)
    p2.xgrid.grid_line_color=None
    p2.ygrid.grid_line_color=None
    p2.axis.visible=False
    p2.add_tile(get_provider(STAMEN_TONER_BACKGROUND),alpha=0.5)
    color_mapper2=LinearColorMapper(palette=palette, low=low, high=high, nan_color='white')
    tracts=p2.patches('xs','ys',source=tract_source,
                     fill_color={'field':field,'transform':color_mapper2},
                     line_color='black',fill_alpha=0.7)
    p2.add_tile(get_provider(STAMEN_TONER_LABELS),alpha=0.8)
    
    p2.add_layout(Title(text='Census Tract {}'.format(tract_df['GEOID'].values[0]),align='left'),'below')
    p2.add_layout(Title(text='Current percent broadband: {:.0f}%'.format(100*tract_df['Pct_Broadband'].values[0]),
                        align='left'),'below')
    p2.add_layout(Title(text=quantity+':',align='left'),'below')
    if quantity=='Predicted New Customers':
        for key in field_dict:
            if not ('Near High' in key):
                p2.add_layout(Title(text='{}: {:,.0f}'.format(key,tract_df[field_dict[key]].values[0]),
                                    align='left',text_font_style='normal',offset=30),'below')
    elif quantity=='Predicted New Annual Revenue':
        for key in field_dict:
            if not ('Near High' in key):
                p2.add_layout(Title(text='{}: ${:,.0f}'.format(key,tract_df[field_dict[key]+'_revenue'].values[0]),
                                    align='left',text_font_style='normal',offset=30),'below')
    if (tract_df[field_dict['All Groups Near High Broadband']].values[0]==
        tract_df[field_dict['All Groups']].values[0]):
        p2.add_layout(Title(text='Near high broadband area: Yes',align='left'),'below')
    else:
        p2.add_layout(Title(text='Near high broadband area: No',align='left'),'below')
    p2.add_layout(Title(text='Median household income: ${:,}'.format(tract_df['Median_Household_Income'].values[0]),
                        align='left'),'below')
    p2.add_layout(Title(text='Percent with device: {:.0f}%'.format(tract_df['Pct_Computer'].values[0]),
                        align='left'),'below')
    
    
    #stacked bar of racial and ethnic makeup
    tract_df['Pct_Other']=tract_df[['Pct_Am_Ind_Non_Hispanic','Pct_Pac_Isl_Non_Hispanic','Pct_Other_Non_Hispanic',
                                    'Pct_TwoPlusRaces_Non_Hispanic']].sum(axis=1)
    re_cats={'Pct_White_Non_Hispanic':'White Non-Hispanic',
             'Pct_Black_Non_Hispanic':'Black Non-Hispanic',
             'Pct_Hispanic':'Hispanic',
             'Pct_Asian_Non_Hispanic':'Asian Non-Hispanic',
             'Pct_Other':'Other'}
    tooltips_p3=[]
    for cat,description in re_cats.items():
        tooltips_p3.append((description,'@'+cat+'{0%}'))
        if cat!='Pct_White_Non_Hispanic':
            tract_df[cat]=tract_df[cat]/100
    
    p3_height=100
    p3=figure(tools='',height=p3_height,width=fig_width,tooltips=tooltips_p3)
    p3.xgrid.grid_line_color=None
    p3.ygrid.grid_line_color=None
    p3.axis.visible=False
    p3.hbar_stack(re_cats.keys(),color=Colorblind[len(re_cats.keys())],height=0.5,
            source=ColumnDataSource(tract_df[re_cats.keys()]))
    p3.add_layout(Title(text='Racial and ethnic makeup:',align='left'),'above')
        
    return p2,p3
    
#find and plot info for the top tracts in the map area
if quantity not in actual_dict:
    st.markdown('')
    st.subheader('Top tracts in this area according to selected target clients')
    df_sorted=map_df.sort_values(by=[field],ascending=False)
    s1a,s1b=tract_info_plot(df_sorted.iloc[0:1])
    if len(df_sorted)>1:
        s2a,s2b=tract_info_plot(df_sorted.iloc[1:2])
    else:
        tract_plot=gridplot([[s1a],[s1b]])
    if len(df_sorted)>2:
        s3a,s3b=tract_info_plot(df_sorted.iloc[2:3])
        tract_plot=gridplot([[s1a,s2a,s3a],[s1b,s2b,s3b]])
    else:
        tract_plot=gridplot([[s1a,s2a],[s1b,s2b]])
    st.bokeh_chart(tract_plot)

    
#####
#Modeling info
#####

st.markdown('')
st.markdown('')
st.markdown('')
st.markdown('')
st.subheader('Modeling Procedure')
st.markdown('Modeling utilized data from the 2019 American Community Survey from the US Census Bureau. 20% of data was withheld for testing, and model training utilized cross-validation to tune hyperparameters. The model predicts the percent of households that have broadband in the tract, and uses information on the median household income, median property value, population density, and the percent of households with a computer or other internet device. The final regression model achieved an $R^2$ value of 0.90 against the withheld testing data.')
#st.image(Image.open('Predicted_vs_Actual.png'))


#####
#Backgound Race/Ethnicity info
#####
st.markdown('')
st.markdown('')
st.markdown('')
st.markdown('')
st.subheader('Existing Racial and Ethnic Disparities in Broadband Access')
st.markdown('Broadband access in Tennessee varies by many factors, including income, urban/rural location, and race and ethnicity. For instance there is noticeably lower broadband access today for those who are Black or African American and those who are Hispanic or Latino. This mirrors national trends as well. These groups also tend to have lower incomes, but controlling for income is not even enough to account for differences in broadband access by race.')
st.markdown('You can see this in the plot below. One clear trend here is that the highest incomes are in census tracts with a low proportion of Black or African American people. You can also see that household broadband generally increases with income. However, even when we consider a single income level straight across the chart, for instance $50,000/year, the percent of households with broadband decreases as the percent of Black or African American residents increases.')
st.markdown('This is one of the opportunities for broadband business expansion that the model is picking up. If two households have the same income and other factors regardless of race or ethnicity, we should expect them to be equally good broadband customers. Not all tracts identified as good expansion opportunities have a large minority population, but since many of the tracts do, we can simultaneously capture new customers and start to narrow existing gaps in access.')
#st.image(Image.open('Black_Income_Broadband.png'))


#Future improvements:

#1. plot of whole state using low-res tract shapefile

#2. change nearby from adjacency to distance (or both)

#3. paired interactive plots/info: click on a tract in the map, get detailed information about that tract next to the map

