What data I need:
* to get the song title and artist name from the Billboard Hot 100.
* to get the right album for the track. (should be the oldest album associated with the track)
* to get the track object given that album.
* to get all artists credited with the track.
	* Should I just get all artists credited with the album instead?
	* I can also get label information


Classes:
1. chart scraper
	* gets the song title and the artist name from the Billboard 100 site.
	* will correct the song title and artist name as necessary
	* saves the CORRECTED track and artist
2. album getter
	* uses Discog to get the correct album
3. credit getter
	* uses Discog to get the credits associated with the album/track