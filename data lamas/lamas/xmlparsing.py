import xml.etree.ElementTree as ET
tree = ET.parse('timeseries_e1.xml')
root = tree.getroot()
print root.tag
print root.attrib
output=[]
for child in root[0]:
  if 'unit' not in child.attrib:
    if 'calc_method' not in child.attrib:
      topic_name = child.attrib['topic_name']
      if not topic_name.endswith('=100'):
        print child.attrib
    else:
      calc_meth = child.attrib['calc_method']
      if not calc_meth.startswith('Index'):
        print child.attrib
  else:
    if child.attrib['unit'] not in output:
      output.append(child.attrib['unit'])
print output
