import xml.etree.cElementTree as ET
import shutil
import os

#copying the original file to deal with exceptions in uploading the data
source_name_prefix = 'timeseries_e_chunk'
target_name_prefix = 'xml_series_chunk'
file_index = 0

while os.path.exists(source_name_prefix + '%d.xml' % file_index):
	source_name = source_name_prefix + '%d.xml' % file_index
	print ('opening: ' + source_name)
	tree = ET.parse(source_name)
	root = tree.getroot()
	for child in root:
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
	tree.write(target_name_prefix + '%d.xml' % file_index)
	file_index+=1

