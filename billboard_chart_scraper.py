# Scrape all Hot 100 weekly charts
# Get date on chart, position, track name, artist

from bs4 import BeautifulSoup as bs
import csv
import json
import requests
import chart_scraper
import album_getter
import time

MUSIC_STORY_KEY = "92d6a47379e2a49a2de9dfcb6fafd70aed8c865e"
MUSIC_STORY_SECRET = "6da57f843c6ed465833ade9796de16fb8b7d9e05"

ROVI_KEY = "hag674r6jkp5cpnkufzqj9yh"
ROVI_SHARED_SECRET = "em2XpwYGvB"

USE_EXISTING_DATA = True

startTime = time.time()

if USE_EXISTING_DATA:
	rows = [["Track", "Artist", "Album", "Year", "Credits"]]
	with open('1990_01_06.csv', 'rb') as csvfile:
	    reader = csv.reader(csvfile)
	    for row in reader:
	    	songTitle, artistName = chart_scraper.getTrackInfo(row)
	    	albumTitle, albumYear = album_getter.getAlbumInfo(songTitle, artistName)
	    	if album_getter.albumIsValid(albumTitle):
	    		rows += [[songTitle, artistName, albumTitle, albumYear]]
	    	else:
	    		songTitle, artistName = chart_scraper.getTrackInfoAdvanced(songTitle, artistName)
	    		albumTitle, albumYear = album_getter.getAlbumInfo(songTitle, artistName)
	    		if album_getter.albumIsValid(albumTitle):
	    			rows += [[songTitle, artistName, albumTitle, albumYear]]
	    		else:
	    			time.sleep(10)
		    		albumTitle, albumYear = album_getter.getAlbumInfoFromDiscogs(songTitle, artistName)
	    			rows += [[songTitle, artistName, albumTitle, albumYear]]
	    	print str(len(rows)-1) + "/100"
else:
	#list of dates for year: http://www.billboard.com/archive/charts/1958/hot-100
	#chart for a week: http://www.billboard.com/charts/hot-100/1958-08-09
	rows = chart_scraper.scrapeChart("1990-01-06")

with open('1990_01_06_results.csv', 'wb') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerows(rows)

print "Completed in: " + str((time.time() - startTime)/60) + " minutes."