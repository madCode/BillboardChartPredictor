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
DISCOGS_API_KEY = "tYjYcYNEYCsKEquvIZHVcsXZCvAgWOTKLqBKABox"
LOWER_CASE_LETTERS = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']
isValid = True
numTracksWithoutAlbum = 0
debug = True
year = 1990
datesAfterYear = 0
discogsClient = None

def getLastFmApiJson(requestURL):
	global isValidRow

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

def getAlbumInfo(songTitle, artistName):
	global numTracksWithoutAlbum
	correctedArtistName = None

	album, year = getAlbumInfoBasic(songTitle, artistName)
	if album == "TRACK NOT FOUND" or album == "ALBUM NOT FOUND":
		print "Trying to correct name"
		songTitle, artistName = getCorrectedArtistAndSong(songTitle, artistName)
		correctedArtistName = getArtistCorrectedName(artistName)
		album, year = getAlbumInfoBasic(songTitle, correctedArtistName)
	if album == "TRACK NOT FOUND" or album == "ALBUM NOT FOUND" or album == "ALBUM HAS WRONG DATE":
		print "Trying discogs"
		if not correctedArtistName:
			correctedArtistName = getArtistCorrectedName(artistName)
		album, year = getAlbumInfoFromDiscogs(songTitle, correctedArtistName)
	if album == "TRACK NOT FOUND" or album == "ALBUM NOT FOUND":
		numTracksWithoutAlbum += 1
	return [album, year]

def getTrackFromDiscogTitle(discogTitle):
	try:
		index = discogTitle.index(" - ")
		return discogTitle[index+3:]
	except ValueError:
		print "No dash in title: " + discogTitle
		return discogTitle

def validRelease(title, currentOptionsList, songTitle):
	return ((title not in currentOptionsList) 
		and (songTitle.lower() not in title.lower()))

def getDiscogAlbumSearchResults(songTitle, artistName):
	potentialAlbums = []
	masterNamesList = []
	searchResults = discogsClient.search(track=songTitle,artist=artistName)
	numRequestsMade = 0

	for result in searchResults:
		numRequestsMade += 1
		if type(result).__name__ == 'Release' or type(result).__name__ == 'Master':
			numRequestsMade += 1
			title = getTrackFromDiscogTitle(result.title)
			if validRelease(title, masterNamesList, songTitle):
				potentialAlbums += [result]
				masterNamesList += [title]
	return (potentialAlbums, masterNamesList, numRequestsMade)

def discogAlbumsWithinYearRange(potentialAlbums, numRequestsMade):
	results, resultsTexts = [], []
	for release in potentialAlbums:
		numRequestsMade += 1
		if type(release).__name__ == 'Release':
			discogYear = release.year
		else:
			discogYear = release.main_release.year
		if int(discogYear) <= year:
			results += [release]
			numRequestsMade += 1
			# I think releases don't need this, only master?
			resultsTexts += [[getTrackFromDiscogTitle(release.title), int(discogYear)]]
	return (results, resultsTexts, numRequestsMade)

def getOldestAlbums(potentialAlbums):
	oldestYear = year + 1
	albums = []
	for album in potentialAlbums:
		if album[1] < oldestYear:
			oldestYear = album[1]
			albums = [album]
		elif album[1] == oldestYear:
			albums += [album]
	return albums

def albumsWithNonZeroYear(potentialAlbums):
	albums = []
	for album in potentialAlbums:
		if album[1] != 0:
			albums += [album]
	return albums

def getAlbumInfoFromDiscogs(songTitle, artistName):
	searchResults = discogsClient.search(track=songTitle,artist=artistName)
	discogYear = 0
	potentialAlbums, masterNamesList, numRequestsMade = getDiscogAlbumSearchResults(songTitle, artistName)
	
	results, resultsTexts, numRequestsMade = discogAlbumsWithinYearRange(potentialAlbums, numRequestsMade)
	
	if numRequestsMade % 60 < 50:
		time.sleep(20)

	if len(resultsTexts) == 1:
		return resultsTexts[0]
	else:
		resultsTexts = albumsWithNonZeroYear(resultsTexts)
		if len(resultsTexts) == 1:
			return resultsTexts[0]
		else:
			resultsTexts = getOldestAlbums(resultsTexts)
			if len(resultsTexts) == 1:
				return resultsTexts[0]
			print len(resultsTexts)
			print resultsTexts
			print "ALBUM NOT FOUND"
			return ["ALBUM NOT FOUND", "ALBUM NOT FOUND"]

def getAlbumTitleFromMusicBrainz(songTitle, artistName):
	print "searching musicbrainz"
	musicbrainzngs.set_useragent("BillboardChartAnalyzer","1","madeehamfg@yahoo.com")
	workList = musicbrainzngs.search_works(work=songTitle, artist=artistName)
	for work in workList['work-list']:
		if songTitle in work['title']:
			print "found potential song"
			for artist in work['artist-relation-list']:
				if artistName in artist['name']:
					print work['title'] + ": " + artist['name']

def getArtistCorrectedName(artistName):
	artistNameRequestURL = ("http://ws.audioscrobbler.com/2.0/?method=artist.getcorrection&api_key=" 
			+ LAST_FM_API_KEY + "&artist=" + artistName + "&format=json")
	artistInfo = requests.get(artistNameRequestURL)
	artistDictionary=json.loads(str(artistInfo.content))
	try:
		return artistDictionary['corrections']['correction']['artist']['name']
	except KeyError as error:
		return artistName

def getAlbumInfoBasic(songTitle, artistName):
	# todo: verify that album is from the right year.
	requestURL = ("http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key=" 
			+ LAST_FM_API_KEY + "&artist=" + artistName 
			+ "&track=" + songTitle + "&format=json")
	trackInfo = requests.get(requestURL)
	if not trackInfo.status_code == 200:
		invalidMessage = ("error with Last.FM api. Response status code: " 
			+ str(trackInfo.status_code)
			+ "\nCheck: http://www.last.fm/api/show/track.getInfo")
		if debug:
			print invalidMessage

	trackDictionary=json.loads(str(trackInfo.content))

	isValid = ('error' not in trackDictionary 
		and 'track' in trackDictionary)
	if not isValid:
		return ["TRACK NOT FOUND", "TRACK NOT FOUND"]
	else:
		isValid = isValid and 'album' in trackDictionary['track']
	
	if isValid:
		album = trackDictionary['track']['album']['title']
		albumYear = getAlbumYear(artistName, album)
		if int(albumYear) > year or albumYear == 0:
			return ["ALBUM HAS WRONG DATE", "ALBUM HAS WRONG DATE"]
		else:
			return [album, albumYear]
	else:
		return ["ALBUM NOT FOUND", "ALBUM NOT FOUND"]

def getAlbumYear(artistName, albumTitle, albumMbid=None):
	if albumTitle != "TRACK OR ALBUM NOT FOUND":
		if (albumMbid):
			requestURL = ("http://ws.audioscrobbler.com/2.0/?method=album.getInfo&api_key=" 
					+ LAST_FM_API_KEY + "&mbid=" + albumMbid)
		else:
			requestURL = ("http://ws.audioscrobbler.com/2.0/?method=album.getInfo&api_key=" 
				+ LAST_FM_API_KEY + "&artist=" + artistName 
				+ "&album=" + albumTitle + "&format=json")
		album = getLastFmApiJson(requestURL)
		if ('album' in album 
			and 'mbid' in album['album'] 
			and len(album['album']['mbid']) > 0):

			return getAlbumYearFromMusicBrainz(album['album']['mbid'])
	return 0

def getAlbumYearFromMusicBrainz(albumMbid):
	global datesAfterYear

	musicbrainzngs.set_useragent("BARRISS_BillboardChartAnalyzer","1","madeehamfg@yahoo.com")
	album = musicbrainzngs.get_release_by_id(albumMbid)
	if 'release' in album and 'date' in album['release']:
		albumYear = album['release']['date'][0:4]
		if int(albumYear) > year:
			datesAfterYear += 1
		return albumYear
	else:
		return 0

def useExistingData(chartRowList):
	time.sleep(20)
	global discogsClient

	results = []
	discogsClient = discogs_client.Client('BARRISS_Billboard 100/0.1', user_token=DISCOGS_API_KEY)

	for row in chartRowList:
		songTitle, artistName = map(cleanDataString, row[0:2])
		albumTitle, albumYear = getAlbumInfo(songTitle, artistName)

		results += [[songTitle, artistName, albumTitle, albumYear]]
	print "Number of rows without album names: " + str(numTracksWithoutAlbum)
	print "Number of rows with newer year: " + str(datesAfterYear)
	return results

def scrapeChart(date_string="1990-01-06"):
	global discogsClient
	results = [["Track", "Artist", "Credits"]]

	discogsClient = discogs_client.Client('Billboard 100/0.1', user_token=DISCOGS_API_KEY)

	#list of dates for year: http://www.billboard.com/archive/charts/1958/hot-100
	#chart for a week: http://www.billboard.com/charts/hot-100/1958-08-09
	page = requests.get("http://www.billboard.com/charts/hot-100/" + date_string)
	soup = bs(page.content, 'html.parser')

	chartRowList = getChartRows(soup)

	for row in chartRowList:
		songTitle, artistName = map(cleanDataString, validateRow(row))
		albumTitle = getAlbumTitle(songTitle, artistName)
		albumYear = getAlbumYear(artistName, albumTitle)

		results += [[songTitle, artistName, albumTitle, albumYear]]
	print "Number of rows without album names: " + str(numTracksWithoutAlbum)
	print "Number of rows with newer year: " + str(datesAfterYear)
	return results