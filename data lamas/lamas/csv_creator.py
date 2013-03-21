import xml.etree.cElementTree as ET
import csv
import shutil
import os

#copying the original file to deal with exceptions in uploading the data
source_name_prefix = 'timeseries_e_chunk'
target_name_prefix = 'csv_e_chunk'
file_index = 0

while os.path.exists(source_name_prefix + '%d.xml' % file_index):
    source_name = source_name_prefix + '%d.xml' % file_index
    print ('opening: ' + source_name)
#create the csv and the csv header
    with open(target_name_prefix + '%d.csv' % file_index, 'wb') as csvfile:    
        spamwriter = csv.writer(csvfile, delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_ALL)
        spamwriter.writerow(['number', 'units', 'description', 'tags', 'source', 'year', 'month', 'day'])

#adding data from xml

        tree = ET.parse(source_name)
        root = tree.getroot()
        for child in root[0]:
          source = 'lamas'
          year = '-1'
          month = '-1'
          day = '-1'
          description = child.attrib['topic_name'] + ', ' + child.attrib['series_name']
          tags = ''
          for attrib in child.attrib:
            tags = tags + attrib + ':' + child.attrib[attrib] + ' '
          if 'unit' in child.attrib:
            unit = child.attrib['unit']
          else:
            if 'calc_method' not in child.attrib:
              topic_name = child.attrib['topic_name']
              if topic_name.endswith('=100'):
                unit='Index'
              else:
                # skip
                unit = 'none'
            else:
              calc_meth = child.attrib['calc_method']
              if calc_meth.startswith('Index'):
                unit = 'Index'
              else:
                #skip
                unit = 'none'
                
          for entry in child:
            if 'time_period' in entry.attrib:
              time = entry.attrib['time_period']
              if time.find('-') != -1:
                year = time.split('-')[0]
                month = time.split('-')[1]
              else :
                year = time
            number = entry.attrib['value']
            spamwriter.writerow([number, unit, description, tags, source,year,month,day])
    file_index+=1

