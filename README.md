isranumbers
===========

Isranumbers is a site that is aimed at collecting and distributing quantitative data about Israel.
It has two main use-cases:
1. Easily search numbers about israel (like population size in 2005).
2. Add entries from external sources (with relevant citations)

The site includes two main data entities:
1. Numbers (which, aside from the number itself, include a description, date (if relevant), units, tags, the author that added the number and the source the number was quoted from.
2. Series, which aggregate a set of numbers either to form a time-series (such as the population of Israel over the years), or a category series (such as the distribution of the population at 2005 by ethnic groups).

The site is designed to be deployed on Google's AppEngine in Python.
The site is currently developed in Hebrew only, though internationalization and support for other languages is on the to-do list.
The data currently on the site is based on files from Israel's Central Bureau of Statistics (CBS) but uploading of data from other sources is also planned.

For developers - the main file of the site is isranumbers.py
Two more files are helper scripts to deal with the xml files the CBS provided.
A sample xml file showing how a series is described when batch loading to the site is sample_series.xml
The other files are the site's html (jinja2 templates) and stylesheets.

Good luck,
Ophir and Uri

