# Takes in a date for the chart
# returns a list of triples: [song, artist, album (empty string if none found)]

# Scrape all Hot 100 weekly charts
# Get date on chart, position, track name, artist

from bs4 import BeautifulSoup as bs
import csv
import json
import musicbrainzngs
import discogs_client
import requests
import time

#http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key=YOUR_API_KEY&artist=cher&track=believe&format=json
LAST_FM_API_KEY = "ec8dbd92b90c63b5b5314884b78d4236"
LOWER_CASE_LETTERS = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']
debug = True

def getLastFmApiJson(requestURL):
	trackInfo = requests.get(requestURL)
	if not trackInfo.status_code == 200:
		invalidMessage = ("error with Last.FM api. Response status code: " 
			+ str(trackInfo.status_code)
			+ "\nRequest was: " + requestURL)
		if debug:
			print invalidMessage

	return json.loads(str(trackInfo.content))

def getChartRows(soup):
	chartRowList = soup.find_all(class_='chart-row__title')
	if not len(chartRowList) == 100:
		invalidMessage = "ROW LIST IS OF INCORRECT LENGTH. EXPECTED 100. ACTUAL: " + len(chartRowList)
		print invalidMessage
	return chartRowList

def validateRow(row):
	# Row should have 1 song title and 1 artist.
	songList = row.find_all(class_='chart-row__song')
	artistList = row.find_all(class_='chart-row__artist')
	isValid = (len(songList) == 1) and (len(artistList) == 1)
	
	if not isValid:
		invalidMessage = "INCORRECT ARTIST/SONG AMOUNT: " + row
		if debug:
			print invalidMessage
	return [songList[0].get_text().strip(), artistList[0].get_text().strip()]

def cleanDataString(dataString):
	# Billboard uses spaces instead of apostrophes for contractions. Which is dumb af.
	lastChar = 'a'
	result = ""
	for char in dataString:
		if lastChar == ' ' and char in LOWER_CASE_LETTERS:
			result += "'" + char
		elif lastChar == ' ':
			result += ' ' + char
		elif char == ' ':
			pass
		else:
			result += char
		lastChar = char
	return result

def getCorrectedArtistAndSong(songTitle, artistName):
	artist = artistName.lower()
	song = songTitle.lower()
	# does the artist have the word "featuring" in it?
	# e.g. Quincy Jones Featuring Ray Charles
	# is there anything in parentheses? e.g. Fiona (Duet with...)
	if " featuring" in artist:
		spliceIndex = artist.index(" featuring")
		artist = artist[0:spliceIndex]
	if " (" in artist:
		spliceIndex = artist.index(" (")
		artist = artist[0:spliceIndex]
	if " (" in song:
		spliceIndex = song.index(" (")
		song = song[0:spliceIndex]
	return [song, artist]

def getArtistCorrectedName(artistName):
	artistNameRequestURL = ("http://ws.audioscrobbler.com/2.0/?method=artist.getcorrection&api_key=" 
			+ LAST_FM_API_KEY + "&artist=" + artistName + "&format=json")
	artistInfo = requests.get(artistNameRequestURL)
	artistDictionary=json.loads(str(artistInfo.content))
	try:
		return artistDictionary['corrections']['correction']['artist']['name']
	except KeyError as error:
		return artistName
