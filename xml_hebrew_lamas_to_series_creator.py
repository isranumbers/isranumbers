import xml.etree.cElementTree as ET
import shutil
import os

#copying the original file to deal with exceptions in uploading the data
#(manipulate original data to be parsible)

source_name = 'timeseries_h'
target_name_prefix = source_name + '_chunk'

source = open(source_name + '.xml', 'rt')
fileindex = 0
#get init:
filestart = []
suffix = []
for line in source:
    if line.startswith('<Series'):
        firstline = line
        break
    else:
        line = line.replace('iso-8859-8-i','iso-8859-8')
        filestart.append(line)

targetname = target_name_prefix + '%d.xml' % fileindex
target = []
target.append(open(targetname,'wt'))

for line in filestart:
    target[fileindex].write(line)
target[fileindex].write(firstline)
count = 0
for line in source:
    if line.startswith('</Data'):
        suffix.append(line)
        break
    line = line.replace('& ', '&amp; ')
    line = line.replace('&glass', '&amp;glass')
    line = line.replace('&artic', '&amp;artic')
    line = line.replace('&scien', '&amp;scien')
    line = line.replace('&Samaria', '&amp;Samaria')
    line = line.replace(chr(0xC5), "")
    line = line.replace('<sub>', "&lt;sub&gt;")
    line = line.replace('</sub>', "&lt;/sub&gt;")

    target[fileindex].write(line)
    count+=1
    if count == 1000:
        for line1 in source:
            line1 = line1.replace('& ', '&amp; ')
            line1 = line1.replace('&glass', '&amp;glass')
            line1 = line1.replace('&artic', '&amp;artic')
            line1 = line1.replace('&scien', '&amp;scien')
            line1 = line1.replace('&Samaria', '&amp;Samaria')
	    line1 = line1.replace(chr(0xC5), "")
	    line1 = line1.replace('<sub>', "&lt;sub&gt;")
	    line1 = line1.replace('</sub>', "&lt;/sub&gt;")
            if line1.startswith('<Series'):
                nextline = line1
                fileindex+=1
                targetname = target_name_prefix + '%d.xml' % fileindex
                target.append(open(targetname,'wt'))
                for line2 in filestart:
                    target[fileindex].write(line2)
                count = 0
                target[fileindex].write(line1)
                break
            else:
                target[fileindex].write(line1)

for line in source:
    suffix.append(line)
for targetf in target:
    for line in suffix:
        targetf.write(line)
    targetf.close()
source.close()

source_name_prefix = 'timeseries_h_chunk'
target_name_prefix = 'hebrew_xml_series_chunk'
file_index = 0

while os.path.exists(source_name_prefix + '%d.xml' % file_index):
	source_name = source_name_prefix + '%d.xml' % file_index
	print ('opening: ' + source_name)
	print ('\n'*10)
	tree = ET.parse(source_name)
	root = tree.getroot()
	target_tree=ET.Element("root")
	for child in root[0]:
  	  labels = ''
  	  for attrib in child.attrib:
    	    labels = labels + attrib + ':' + child.attrib[attrib] + ' '
  	  child.set('description', ', '.join(child.attrib['topic_name'].split(' - ')[2:]) + ', ' + child.attrib['series_name'])
	  child.set('labels', labels)
	  child.set('series_type', 'time series')
	  child.set('source', 'lamas')
	  if not 'unit' in child.attrib:
	    if 'calc_method' not in child.attrib:
	      topic_name = child.attrib['topic_name']
	      if topic_name.endswith('=100'):
		child.set('unit', 'Index')
	      else:
		child.set('unit', 'undefined')
	    else:
	      calc_meth = child.attrib['calc_method']
	      if calc_meth.startswith('Index'):
		child.set('unit', 'Index')
	      else:
		child.set('unit', 'undefined')
	  list_of_new_attributes = ['description', 'labels', 'series_type', 'source', 'unit'] 
	  attribs_to_remove = []
	  for attrib in child.attrib:
	    if attrib not in list_of_new_attributes:
	      attribs_to_remove.append(attrib)
	  for attrib in attribs_to_remove:
	      del child.attrib[attrib] 
	  target_tree.append(child)
	target_file = ET.ElementTree(target_tree)	
	target_file.write(target_name_prefix + '%d.xml' % file_index)
	file_index+=1
