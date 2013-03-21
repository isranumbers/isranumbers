#manipulate original data to be parsible
import shutil

source_name = './timeseries_e'
target_name_prefix = source_name + '_chunk'

source = open(source_name + '.xml', 'r')
fileindex = 0
#get init:
filestart = []
suffix = []
for line in source:
    if line.startswith('<Series'):
        firstline = line
        break
    else:
        line = line.replace('iso-8859-8-i','utf-8')
        filestart.append(line)

targetname = target_name_prefix + '%d.xml' % fileindex
target = []
target.append(open(targetname,'w'))

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
    line = line.replace(chr(0xa0), ' ')
    line = line.replace(chr(0xb7), ' ')
    line = line.replace(chr(0xee), '')
    line = line.replace(chr(0x96), ' ')
    line = line.replace(chr(0x92), "'")

    target[fileindex].write(line)
    count+=1
    if count == 10000:
        for line1 in source:
            line1 = line1.replace('& ', '&amp; ')
            line1 = line1.replace('&glass', '&amp;glass')
            line1 = line1.replace('&artic', '&amp;artic')
            line1 = line1.replace('&scien', '&amp;scien')
            line1 = line1.replace(chr(0xa0), ' ')
            line1 = line1.replace(chr(0xb7), ' ')
            line1 = line1.replace('&Samaria', '&amp;Samaria')
            line1 = line1.replace(chr(0xee), '')
            line1 = line1.replace(chr(0x96), ' ')
            line1 = line1.replace(chr(0x92), "'")
            if line1.startswith('<Series'):
                nextline = line1
                fileindex+=1
                targetname = target_name_prefix + '%d.xml' % fileindex
                target.append(open(targetname,'w'))
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
# for line in source:
  # target.write(line.replace('\a0', ' '))
