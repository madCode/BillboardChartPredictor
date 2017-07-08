# Takes in a date for the chart
# returns a list of triples: [song, artist, album (empty string if none found)]

# Scrape all Hot 100 weekly charts
# Get date on chart, position, track name, artist

from bs4 import BeautifulSoup as bs
import csv
import json
import musicbrainzngs
import documents.discogs_client.discogs_client as discogs_client
import requests
import time
import random

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

startedTime = None

def maybeWait(seconds, threshold, requestsMade):
	return
	# rate = requestsMade / (time.time() - startedTime)
	# rand = random.random()
	# # if rate > 50:
	# seconds = 50
	# if requestsMade > 50 and rate > 30:
	# 	print str(requestsMade) + " requests made at rate " + str(rate) + ". Waiting for " + str(seconds) + " seconds."
	# 	time.sleep(seconds)

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

def albumIsValid(albumTitle):
	return not (albumTitle == "ALBUM OR TRACK NOT FOUND" 
				or albumTitle == "ALBUM HAS WRONG DATE")

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
	# maybe trim, remove punctuation and lower case, and then compare track names
	potentialAlbums = []
	masterNamesList = []
	searchResults = discogsClient.search(track=songTitle,artist=artistName)
	numRequestsMade = 0

	for result in searchResults:

		maybeWait(5, 0.15, numRequestsMade)

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

		maybeWait(5, 0.1, numRequestsMade)

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
	global discogsClient, startedTime
	startedTime = time.time()

	discogsClient = discogs_client.Client('Billboard 100/0.1', user_token=DISCOGS_API_KEY)
	searchResults = discogsClient.search(track=songTitle,artist=artistName)
	discogYear = 0
	potentialAlbums, masterNamesList, numRequestsMade = getDiscogAlbumSearchResults(songTitle, artistName)
	
	maybeWait(20, 0.4, numRequestsMade)

	results, resultsTexts, numRequestsMade = discogAlbumsWithinYearRange(potentialAlbums, numRequestsMade)

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
			return [resultsTexts, "ALBUM NOT FOUND"]
			# print "ALBUM NOT FOUND"
			# return ["ALBUM NOT FOUND", "ALBUM NOT FOUND"]

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

def getAlbumInfo(songTitle, artistName):
	# todo: verify that album is from the right year.
	requestURL = ("http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key=" 
			+ LAST_FM_API_KEY + "&artist=" + artistName 
			+ "&track=" + songTitle + "&format=json")
	trackDictionary = getLastFmApiJson(requestURL)

	isValid = ('error' not in trackDictionary 
		and 'track' in trackDictionary
		and 'album' in trackDictionary['track'])
	
	if isValid:
		album = trackDictionary['track']['album']['title']
		albumYear = getAlbumYear(artistName, album)
		if int(albumYear) > year or albumYear == 0:
			return ["ALBUM HAS WRONG DATE", "ALBUM HAS WRONG DATE"]
		else:
			return [album, albumYear]
	else:
		return ["ALBUM OR TRACK NOT FOUND", "ALBUM OR TRACK NOT FOUND"]

def getAlbumYear(artistName, albumTitle, albumMbid=None):
	if not albumMbid:
		requestURL = ("http://ws.audioscrobbler.com/2.0/?method=album.getInfo&api_key=" 
			+ LAST_FM_API_KEY + "&artist=" + artistName 
			+ "&album=" + albumTitle + "&format=json")
		album = getLastFmApiJson(requestURL)
		if ('album' in album 
			and 'mbid' in album['album'] 
			and len(album['album']['mbid']) > 0):

			albumMbid = album['album']['mbid']

	if albumMbid:
		return getAlbumYearFromMusicBrainz(albumMbid)
	else:
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