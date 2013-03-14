#manipulate original data to be parsible
import shutil

source_name = 'timeseries_e'
target_name = source_name + '_manipulated.xml'

source = open(source_name + '.xml', 'r')
target = open(target_name, 'w')
target.write(source.readline().replace('8859-8-i','8859-8'))
for line in source:
  target.write(line.replace('&', '&amp;amp;'))
