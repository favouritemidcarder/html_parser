import logging
import requests
from bs4 import BeautifulSoup, Tag
import cssutils
from PIL import Image
from io import BytesIO
import re
import os

directory = 'page'
#######LOGGING##########
logging.basicConfig(
    filename='Html Approach',
    filemode='a',
    #format='%(asctime)s %(levelname)-8s %(message)s',
    format='%(asctime)s.%(msecs)03d  %(levelname)-8s %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S'
)

max_chunk_len=1200
extra_chunk_len_for_img_or_tb = 200

def recursive_font_weight_finder(tag):
    if isinstance(tag, Tag):
        if tag.has_attr('style') and 'font-weight' in tag['style']:
            css= cssutils.parseStyle(tag['style'])
            return css['font-weight']
        else:
            for child in tag.children:
                return recursive_font_weight_finder(child)
    else:        
        return None
    


def extract_text_from_url(url):
    # Fetch the image from the URL
    response = requests.get(url,headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
    if response.status_code != 200:
        return "Failed to retrieve image"
    
    # Open the image using PIL
    image = Image.open(BytesIO(response.content))
    
    # Use Tesseract to extract text
    #text = pytesseract.image_to_string(image)
    #return text


def strip_html_tags_with_bs(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
     # If you specifically want to remove `ix` tags or any other specific tags
       
    tags_to_remove = ['title','noscript','ix:header','style','script']
    for tag in tags_to_remove:
        for tag in soup.find_all(tag):  # Replace 'ix:nonnumeric' with whatever specific tag you want to remove
            tag.extract()
    
    #for tag in soup.find_all(lambda tag: tag.name and tag.name.startswith('ix:')):
    #    tag.extract()

    for anchor_tag in soup.find_all('a'):
        ## ADDED BUG FIX TO PICK <a name> redirections
        if anchor_tag.has_attr('name'):
                new_tag=soup.new_tag("citation")
                new_tag.string = "##CITATION ##CITATION"+anchor_tag['name']+"##CITATION-END"
                anchor_tag.insert_before(new_tag)
            
        if anchor_tag.text.lower()=='table of contents':
            anchor_tag.extract()

    for any_tag_with_id in soup.find_all(id=True):
        tag_text=any_tag_with_id.text
        if any_tag_with_id.name.startswith('ix:')==False: 
            new_tag=soup.new_tag("citation")
            new_tag.string = "##CITATION ##CITATION"+any_tag_with_id['id']+"##CITATION-END"
            any_tag_with_id.insert_before(new_tag)
            #any_tag_with_id.string=("##CITATION "+any_tag_with_id['id']+"\n"+tag_text+"\n")

    for div_tag in soup.find_all(['div']):

        if len(div_tag.findAll(recursive=False))!=0 and div_tag.parent.name not in ['tr','td','table','tbody'] and len(div_tag.findAll(recursive=False))==len(div_tag.findAll('font',recursive=False)):
             div_tag.string = (div_tag.get_text(separator=' ',strip=True).replace("\n"," "))

    for table_tag in soup.find_all('table'):
        #print("table detected")
        header_row=1
        initial_font_weight=0
        non_empty_row_counter=1
        isHeader=True
        headerDetection=True
        hasIntermittentHeader=False
        for table_row in table_tag.find_all('tr'):
            for table_cell in table_row.find_all(['td','th']):
                if table_cell.name=='th':
                    if headerDetection: 
                        headerDetection=False
                        header_row=non_empty_row_counter
                    elif isHeader==False:
                        hasIntermittentHeader=True
                elif headerDetection==False and table_cell.name=='td':   
                    isHeader=False
                
                if headerDetection:
                    tags_font_weight=recursive_font_weight_finder(table_cell)
                    #print("tags_font_weight-",tags_font_weight, " initial_font_weight-",initial_font_weight, " isHeader-",isHeader," hasIntermittentHeader-",hasIntermittentHeader," text-",table_cell.text, " len-",len(table_cell.text.strip()) )
                    if tags_font_weight and len(table_cell.text.strip())>0: 
                        if initial_font_weight==0:
                            initial_font_weight=tags_font_weight
                        elif initial_font_weight==tags_font_weight:
                            header_row=non_empty_row_counter
                            if isHeader==False:
                                hasIntermittentHeader=True
                        elif initial_font_weight!=tags_font_weight:
                            isHeader=False
                    elif tags_font_weight is None and len(table_cell.text.strip())>0 and initial_font_weight!=0:
                        isHeader=False
                #table_cell_content=table_cell.text
                table_cell_content = table_cell.get_text(separator=" ",strip=True)
                table_cell.replace_with(table_cell_content+" | ")
            table_row_content=table_row.get_text(strip=True).replace("\u200b",'')
            #print("row_content-"+table_row_content)
            if len(table_row_content.replace('|','').strip())>0:
                table_row.replace_with((("##HEADER " if hasIntermittentHeader==False else "##HEADER-INTERMITTENT ") if header_row==non_empty_row_counter else "") + table_row_content+"\n")
                non_empty_row_counter+=1
            else:
                table_row.replace_with('')
        table_tag_content=table_tag.get_text(separator="\n",strip=True)
        #print("table_content-"+table_tag_content)

        if len(table_tag_content.strip())>0:
            #print("length ke if mein aaya")
            if table_tag_content.count("##HEADER ")==(non_empty_row_counter-1):
                table_tag_content=table_tag_content.replace("\n##HEADER ","\n")
                #print("strip HEADER from every row but first logic")
            if non_empty_row_counter==2:
                table_tag.replace_with("\n"+table_tag_content.replace("##HEADER","").replace('|',''))
            else:
                #find until 5 previous tags to get text right above table
                found_table_pretext = False
                table_pretext=""
                previous_tag = table_tag.find_previous()
                previous_tag_iter=1
                while previous_tag_iter<=5 and previous_tag:
                    previous_tag = previous_tag.find_previous()
                
                    if previous_tag:
                        #print("previous_tag-"+previous_tag.name)
                        previous_tag_content = previous_tag.get_text(separator=" ",strip=True)
                        if len(previous_tag_content)==0 or previous_tag.name =='table' or previous_tag.name.startswith('ix:') or previous_tag_content.find('|')!=-1 or previous_tag_content.find('##CITATION')!=-1:
                            continue
                        #print("extracted-"+previous_tag.name+'-'+previous_tag_content)
                        if len(previous_tag_content)>10:# and (previous_tag_content.find(':')!=-1 or previous_tag_content.find('.')!=-1 or previous_tag_content.find('-')!=-1):
                            found_table_pretext=True
                            table_pretext=previous_tag_content
                            previous_tag.extract()
                            break
                        previous_tag_iter+=1
                    else:
                        break
                #print("---------------")    
                optional_pretext = ("##PRETEXT-START "+table_pretext+"##PRETEXT-END\n") if found_table_pretext and len(table_pretext)>0 else ""
                #print("optional_pretext-"+optional_pretext)
                table_tag.replace_with("\n##TABLE-START\n"+optional_pretext+table_tag_content+"\n##TABLE-END\n")
        else:
            #print("empty table detected")
            table_tag.replace_with("")
        #if anchor_tag.has_attr('href') and anchor_tag['href'].startswith("#"):
            #anchor_tag.replace_with("##LINKS TO "+anchor_tag['href']+"\n"+anchor_tag.text+"\n")
    
    #for img_tag in soup.find_all('img'):
    #    if img_tag.has_attr('src'):
    #        img_tag.replace_with("\n##IMAGE-START\n"+ extract_text_from_url(url[:url.rfind('/')]+"/"+img_tag['src'])+"##IMAGE-END\n")
    #print("---------------")
    #print(soup.get_text())
    #print("---------------")
    for div_tag in soup.find_all(['div']):
        if div_tag.findAll(['span']):    
            div_tag.replace_with(div_tag.get_text(separator=' '))
        #if len(div_tag.findAll(recursive=False))!=0 and len(div_tag.findAll(recursive=False))==len(div_tag.findAll('font',recursive=False)):
             #div_tag.replace_with(div_tag.get_text(separator=' ',strip=True).replace("\n"," "))
    
    for p_tag in soup.find_all('font'):
            p_tag.replace_with(p_tag.get_text(separator=' ',strip=True).replace("\n"," "))
    
   
    #print(soup.get_text())
    # Extracting text content
    text_content = soup.get_text(separator='\n\n',strip=True)
    text_content = text_content.replace('\xa0','').replace("\u200b",'')
    

    return text_content

def fit_table(table_row_start,table_repeatable_top_part_strip,chunks,present_citation,key,present_chunk):
    table_data_rows = table_row_start.split("\n")
    row_index=0
    while row_index < len(table_data_rows):
        current_row = table_data_rows[row_index]+"\n"
        if current_row.startswith("##HEADER-INTERMITTENT"):
            row_iter_index = row_index
            continuous_header_intermitents_strip = current_row.replace("##HEADER-INTERMITTENT","")
            continuous_header_intermitents_index = row_index
            intermittent_rows=current_row.replace("##HEADER-INTERMITTENT","")
            nonHeaderRowFound = False
            finalHeaderIntermittentFound = False
            while finalHeaderIntermittentFound==False and row_iter_index < (len(table_data_rows)-1):
                row_iter_index+=1
                #intermittent_rows+=table_data_rows[row_iter_index]+"\n"
                #first data row found
                if table_data_rows[row_iter_index].startswith("##HEADER-INTERMITTENT")==False and table_data_rows[row_iter_index].startswith("##TABLE-END")==False:
                    nonHeaderRowFound=True
                    intermittent_rows+=table_data_rows[row_iter_index]+"\n"
                
                #next header intermittent or table end found after data row
                elif (table_data_rows[row_iter_index].startswith("##HEADER-INTERMITTENT") or table_data_rows[row_iter_index].startswith("##TABLE-END")) and nonHeaderRowFound:
                    finalHeaderIntermittentFound = True

                #conitnous header intermittents found    
                elif nonHeaderRowFound==False and table_data_rows[row_iter_index].startswith("##HEADER-INTERMITTENT"):
                    continuous_header_intermitents_strip+=table_data_rows[row_iter_index].replace("##HEADER-INTERMITTENT","")+"\n"
                    intermittent_rows+=table_data_rows[row_iter_index].replace("##HEADER-INTERMITTENT","")+"\n"
                    continuous_header_intermitents_index=row_iter_index

                #intermittent_rows_strip = intermittent_rows.replace("##HEADER-INTERMITTENT","")
            row_index=row_iter_index#+1
            if (len(present_chunk)+len(intermittent_rows))<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                present_chunk+=intermittent_rows
            elif (len(table_repeatable_top_part_strip)+len(intermittent_rows))<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                chunks.append({"content":present_chunk, "citation":present_citation})     
                present_chunk=table_repeatable_top_part_strip+intermittent_rows
                present_citation=key
            else :
                minimum_header_interminttent_only_info = continuous_header_intermitents_strip+table_data_rows[continuous_header_intermitents_index+1]
                if (len(present_chunk)+len(minimum_header_interminttent_only_info))<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                    present_chunk+=continuous_header_intermitents_strip
                    for row_index_iter in range(continuous_header_intermitents_index+1,row_index):
                        if (len(present_chunk)+len(table_data_rows[row_index_iter]))<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                            present_chunk+=table_data_rows[row_index_iter]+"\n"
                        else: 
                            chunks.append({"content":present_chunk, "citation":present_citation})     
                            present_chunk=table_repeatable_top_part_strip+continuous_header_intermitents_strip+table_data_rows[row_index_iter]
                            present_citation=key

        elif (len(present_chunk)+len(current_row))<=max_chunk_len+extra_chunk_len_for_img_or_tb:
            present_chunk+=current_row
            row_index+=1
        else: 
            chunks.append({"content":present_chunk, "citation":present_citation})     
            present_chunk=table_repeatable_top_part_strip+current_row
            present_citation=key
            row_index+=1
    return present_citation,present_chunk

def readjust_table_or_image(pre_break_text,post_break_text,chunks,key,present_chunk,present_citation):
    
    #check if table
    table_start_index = pre_break_text.rfind("##TABLE-START")
    table_end_index = pre_break_text.rfind("##TABLE-END")
    #print("Table mili kya - "+str(table_start_index)+" "+str(table_end_index))
    #check if image
    image_start_index = pre_break_text.rfind("##IMAGE-START")
    image_end_index = pre_break_text.rfind("##IMAGE-END")
 
    #this chunk has table started but not ended
    if table_start_index >table_end_index:
        
        #print("Table is cut")
        #pre_table_part=pre_break_text[:table_start_index]
        table_full_part = pre_break_text[table_start_index:]+post_break_text[:post_break_text.find("##TABLE-END")+11]
        post_table_part = post_break_text[post_break_text.find("##TABLE-END")+11:]
        table_full_part_strip = table_full_part.replace('##HEADER-INTERMITTENT ','').replace('##HEADER ','')

        if present_citation is None:
            present_citation = key
        
        if (len(present_chunk)+len(table_full_part_strip.replace("##PRETEXT-START ","").replace("##PRETEXT-END","")))<=max_chunk_len+extra_chunk_len_for_img_or_tb:
            print("Table can fit in current chunk")
            table_full_part_strip = table_full_part_strip.replace("##PRETEXT-START ","")
            if table_full_part_strip.find("##PRETEXT-END")!=-1:
                table_full_part_strip = table_full_part_strip.replace("##TABLE-START\n","")
                table_full_part_strip = table_full_part_strip.replace("##PRETEXT-END","\n##TABLE-START")
            print("table_full_part_strip-",table_full_part_strip)
            return present_chunk+table_full_part_strip,present_citation,post_table_part
        
        elif len(table_full_part_strip.replace("##PRETEXT-START ","").replace("##PRETEXT-END","")) <= (max_chunk_len+extra_chunk_len_for_img_or_tb):
            print("Table can fit in new one chunk")
            chunks.append({"content":present_chunk, "citation":present_citation})
            table_full_part_strip = table_full_part_strip.replace("##PRETEXT-START ","")
            if table_full_part_strip.find("##PRETEXT-END")!=-1:
                table_full_part_strip = table_full_part_strip.replace("##TABLE-START\n","")
                table_full_part_strip = table_full_part_strip.replace("##PRETEXT-END","\n##TABLE-START")
            present_chunk=table_full_part_strip
            return present_chunk,key,post_table_part
        else:
            print("Table has to be cut - no other way")
           
            '''table_pretext = ""
            table_header=""
            if table_full_part.find("##PRETEXT-START")!=-1:
                table_pretext = table_full_part[table_full_part.find("##PRETEXT-START"):table_full_part.find("##PRETEXT-END")+14]'''
            
            #if table_full_part.find("##HEADER")!=-1:
                
                #table_header = table_full_part[table_full_part.find("##HEADER "):table_post_last_header.find('\n')+1+table_full_part.rfind("##HEADER ")]
            
            
            #table_repeatable_top_part = table_full_part[:table_post_last_header.find('\n')+1+table_full_part.rfind("##HEADER ")]
            #table_repeatable_top_part_strip = table_repeatable_top_part.replace("##PRETEXT-START","").replace("##PRETEXT-END","").replace("##HEADER ","")
            
            #minimum_table_part_strip = minimum_table_part.replace("##PRETEXT-START ","").replace("##PRETEXT-END","").replace("##HEADER ","")
            
            ######lokesh clean variables start
            pretext_only=""
            if table_full_part.find("##PRETEXT-START ")!=-1:
                    pretext_only=table_full_part[table_full_part.find("##PRETEXT-START "):table_full_part.find("##PRETEXT-END\n")+14]
                    pretext_only = pretext_only.replace("##PRETEXT-START ","").replace("##PRETEXT-END","")
            
            table_post_last_header = table_full_part[table_full_part.rfind("##HEADER "):]
            table_headers = table_full_part[table_full_part.find("##HEADER "):table_post_last_header.find('\n')+table_full_part.rfind("##HEADER ")+1].replace("##HEADER ","")
            table_row_start = table_full_part[table_post_last_header.find('\n')+table_full_part.rfind("##HEADER ")+1:]

            table_repeatable_top_part = pretext_only+"##TABLE-START\n"+table_headers
            first_data_row  = table_row_start[:table_row_start.find('\n')+1]
            
            print("pretext_only-",pretext_only)
            print("table_headers-",table_headers)
            print("table_row_start-",table_row_start)
            print("table_repeatable_top_part-",table_repeatable_top_part)
            print("first_data_row-",first_data_row)

            if (len(present_chunk)+len(table_repeatable_top_part)+len(first_data_row))<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                print("mts can be inserted in present chunk")
                present_chunk+=table_repeatable_top_part
                present_citation,present_chunk  = fit_table(table_row_start,table_repeatable_top_part,chunks,present_citation,key,present_chunk)
            
            elif len(table_repeatable_top_part)+len(first_data_row)<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                print("mts can be inserted in one new chunk")
                chunks.append({"content":present_chunk, "citation":present_citation})     
                present_chunk=table_repeatable_top_part
                present_citation,present_chunk  = fit_table(table_row_start,table_repeatable_top_part,chunks,present_citation,key,present_chunk)
            
            else:
                print("mts need to be broken anyhow")
                
                '''if table_repeatable_top_part.find("##PRETEXT-START ")!=-1:
                    table_repeatable_top_part=table_repeatable_top_part[table_repeatable_top_part.find("##PRETEXT-END\n")+14:]
                table_repeatable_top_part_strip = table_repeatable_top_part.replace("##HEADER ","")
                
                
                minimum_table_part_strip = table_repeatable_top_part_strip+table_row_start[:table_row_start.find('\n')+1]'''
                
                ##accomodate pretext before tackling table
                if len(present_chunk)+len(pretext_only)<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                    present_chunk+=pretext_only
                else:
                    while len(pretext_only)>0:
                        full_stop_search = re.search("[a-z][.]\s+[A-Z]",pretext_only)
                        first_full_stop_index = full_stop_search.start()+3 if full_stop_search else len(pretext_only)
                        if len(present_chunk)+len(pretext_only[:first_full_stop_index])>max_chunk_len:
                            chunks.append({"content":present_chunk, "citation":present_citation})
                            present_chunk=""
                            present_citation=key
                        
                        present_chunk+=pretext_only[:first_full_stop_index]
                        pretext_only = pretext_only[first_full_stop_index:]
                
                minimum_table_part_without_pretext = pretext_only+"##TABLE-START\n"+table_headers
                
                if (len(present_chunk)+len(minimum_table_part_without_pretext)+len(first_data_row))<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                    print("mts no pretext can be inserted in present chunk")
                    present_chunk+=minimum_table_part_without_pretext
                    present_citation,present_chunk  = fit_table(table_row_start,minimum_table_part_without_pretext,chunks,present_citation,key,present_chunk)
                
                elif len(minimum_table_part_without_pretext)+len(first_data_row)<=max_chunk_len+extra_chunk_len_for_img_or_tb:
                    print("mts no pretext can be inserted in one new chunk")
                    chunks.append({"content":present_chunk, "citation":present_citation})     
                    present_chunk=minimum_table_part_without_pretext
                    present_citation,present_chunk  = fit_table(table_row_start,minimum_table_part_without_pretext,chunks,present_citation,key,present_chunk)
                else:
                    print("mts no pretext needs to be broken anyhow")
                    full_table_strip = minimum_table_part_without_pretext+table_row_start.replace("##HEADER-INTERMITTENT","")
                    chunks.append({"content":present_chunk, "citation":present_citation})
                    present_chunk=""
                    present_citation=key

                    final_char_break="\n"
                    first_newline_index_header = minimum_table_part_without_pretext.find("\n")+1 if minimum_table_part_without_pretext.find("\n")!=-1 else len(minimum_table_part_without_pretext)
                    first_newline_index_data = table_row_start.replace("##HEADER-INTERMITTENT","").find("\n")+1 if table_row_start.replace("##HEADER-INTERMITTENT","").find("\n")!=-1 else len(table_row_start.replace("##HEADER-INTERMITTENT",""))
                    #first_fullstop_index = full_table_strip.find(".")+1 if full_table_strip.find(".")!=-1 else len(full_table_strip)
                    #final_break_index=first_newline_index
                    #print("len-",len(full_table_strip[:first_newline_index]))
                    if len(minimum_table_part_without_pretext[:first_newline_index_header])>(max_chunk_len+extra_chunk_len_for_img_or_tb) or len(table_row_start[:first_newline_index_data])>(max_chunk_len+extra_chunk_len_for_img_or_tb) :
                        #final_break_index=first_fullstop_index
                        final_char_break="."
                    print("final_char_break-",final_char_break)
                    while len(full_table_strip)>0:
                        #first_newline_index = full_table_strip.find("\n")+1 if full_table_strip.find("\n")!=-1 else len(full_table_strip)
                        #first_fullstop_index = full_table_strip.find(".")+1 if full_table_strip.find(".")!=-1 else len(full_table_strip)
                        
                        final_break_index=full_table_strip.find(final_char_break)+1 if full_table_strip.find(final_char_break)!=-1 else len(full_table_strip)
                        #if len(full_table_strip[:final_break_index])>max_chunk_len+extra_chunk_len_for_img_or_tb:
                        #    final_break_index=first_fullstop_index
                        
                        
                        if len(present_chunk)+len(full_table_strip[:final_break_index])>max_chunk_len+extra_chunk_len_for_img_or_tb:
                            chunks.append({"content":present_chunk, "citation":present_citation})
                            present_chunk=""
                            present_citation=key
                        present_chunk+=full_table_strip[:final_break_index]
                        full_table_strip = full_table_strip[final_break_index:]
                        
            
        return present_chunk,present_citation,post_table_part
        
        
    #this chunk has image started but not ended
    elif image_start_index > image_end_index:
        #print("Image is cut")
        pre_image_part = pre_break_text[:image_start_index]
        image_start_part = pre_break_text[image_start_index:]
        image_end_part = post_break_text[:post_break_text.find("##IMAGE-END")+11]
        post_image_part = post_break_text[post_break_text.find("##IMAGE-END")+11:]

        
        if present_citation is None:
            present_citation = key
        
        if len(present_chunk)+len(image_start_part)+len(image_end_part) <=max_chunk_len:
            #print("Image can fit in current chunk")
            pre_break_text += image_end_part
            post_break_text=post_image_part

        if len(image_start_part)+len(image_end_part) <= max_chunk_len+extra_chunk_len_for_img_or_tb:
            #print("Image can fit in one chunk")
            chunks.append({"content":present_chunk+pre_image_part, "citation":present_citation})
            pre_break_text=image_start_part+image_end_part
            present_chunk=""
            present_citation=key
            post_break_text=post_image_part
        
        else:
            #print("Image has to be cut - no other way")
            
            if len(pre_image_part)+len(present_chunk) > max_chunk_len:
                chunks.append({"content":present_chunk, "citation":present_citation})
                present_chunk=""
                present_citation=None
                
            present_chunk+=pre_image_part
            if present_citation is None:
                present_citation=key
            
            image_full_part=image_start_part+image_end_part
            while len(image_full_part)>0:
                full_stop_search = re.search("[a-z][.]\s[A-Z]",image_full_part)
                first_full_stop_index = full_stop_search.start()+3 if full_stop_search else len(image_full_part)
                first_newline_index = image_full_part.find("\n")+1 if image_full_part.find("\n")!=-1 else len(image_full_part)
                

                min_break_index = min(first_full_stop_index,first_newline_index)

                pre_break_text_img = image_full_part[:min_break_index]
                post_break_text_img = image_full_part[min_break_index:]

                if len(pre_break_text_img)+len(present_chunk) > (max_chunk_len+extra_chunk_len_for_img_or_tb):
                    chunks.append({"content":present_chunk, "citation":key})
                    present_chunk="##IMAGE-START\n"
                    
                
                present_chunk+=pre_break_text_img
                image_full_part = post_break_text_img
                

            return present_chunk,present_citation,post_image_part
        
    
    if len(pre_break_text)+len(present_chunk) > max_chunk_len and len(present_chunk)>0: ##SNEHA BUG FIX
        chunks.append({"content":present_chunk, "citation":present_citation})
        present_chunk=""
        present_citation=None
                
    present_chunk+=pre_break_text
    if present_citation is None:
        present_citation=key

    
    
    return present_chunk,present_citation,post_break_text



def chunking(url_content):
    url_citation_list = url_content.split("##CITATION ")
    #logging.info(url_citation_list)
    citation_dict={}
    for citation_content in url_citation_list:
        if len(citation_content)>0:
            if citation_content.startswith("##CITATION"):
                citation_content = citation_content[10:]
                citation_dict[citation_content[:citation_content.find("##CITATION-END")]]=citation_content[citation_content.find("##CITATION-END")+14:]
            else:
                citation_dict['']=citation_content
    #logging.info(citation_dict)
    chunks=[]
    present_chunk=""
    present_citation=None
    for key in citation_dict.keys():
        to_add = citation_dict[key]
        
        while len(to_add)>0:
            #find nearest break point
            full_stop_search = re.search("[a-z][.]\s+[A-Z]",to_add)
            first_full_stop_index = full_stop_search.start()+3 if full_stop_search else len(to_add)
            first_newline_index = to_add.find("\n")+1 if to_add.find("\n")!=-1 else len(to_add)
            first_section_index = to_add.find("\n\n")+2 if to_add.find("\n\n")!=-1 else len(to_add)

            min_break_index = min(first_full_stop_index,first_newline_index,first_section_index)

            if min_break_index > max_chunk_len:
                print("in min break index if ;")
                first_semicolon_index = to_add.find(";")+1 if to_add.find(";")!=-1 else len(to_add)
                first_fullstop_index = to_add.find(".")+1 if to_add.find(".")!=-1 else len(to_add)
                min_break_index = min(first_semicolon_index,first_fullstop_index)
                if min_break_index > max_chunk_len:
                    min_break_index = to_add.find(",")+1 if to_add.find(",")!=-1 else len(to_add)
            
            pre_break_text = to_add[:min_break_index]
            post_break_text = to_add[min_break_index:]
            present_chunk,present_citation,to_add=readjust_table_or_image(pre_break_text,post_break_text,chunks,key,present_chunk,present_citation)
        
    if len(present_chunk)>0:
        chunks.append({"content":present_chunk, "citation":present_citation})
    return chunks


# Test
headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

def main():
    for filename in os.listdir(directory):
        f = os.path.join(directory, filename)
        if os.path.isfile(f):
            HtmlFile = open(f, 'r', encoding='utf-8')
            html_content = HtmlFile.read()

    logging.info("-----------------------------")
    url_content = strip_html_tags_with_bs(html_content)
    logging.info(url_content)
    chunked_ar = chunking(url_content)
    logging.info("-----------------------------")
 
    for chunk in chunked_ar:
        chunk['content'] = re.sub(r'\n{3,}', '\n\n', chunk['content'])
        chunk['length'] = len(chunk['content'])
        if(len(chunk['content'])>1400):
            print("citation- " + chunk['citation']+ " length-"+str(len(chunk['content'])))
        if chunk['content'].count('##TABLE-END') > chunk['content'].count('##TABLE-START'):
            print("citation- " + chunk['citation']+ " length-"+str(len(chunk['content']))+" no start to end")

    logging.info(chunked_ar)

main()
