# Copyright (c) 2009 StudioNow, Inc <patrick@studionow.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import hashlib
import simplejson
import urllib2
import urllib
import cookielib
from pybrightcove       import config, UserAgent, ItemCollection
from pybrightcove.video import Video
from pybrightcove.enums import SortByType, SortByOrderType
from pybrightcove.enums import PublicVideoFieldsEnum
from pybrightcove.exceptions import BrightcoveError


class Connection(object):

    def __init__(self, read_token=None, write_token=None, **kwargs):
        if read_token:
            self.read_token = read_token
        elif config.has_option('Connection', 'read_token'):
            self.read_token = config.get('Connection', 'read_token')

        if write_token:
            self.write_token = write_token
        elif config.has_option('Connection', 'write_token'):
            self.write_token = config.get('Connection', 'write_token')

        if 'read_url' in kwargs:
            self.read_url = kwargs['read_url']
        elif config.has_option('Connection', 'read_url'):
            self.read_url = config.get('Connection', 'read_url')

        if 'write_url' in kwargs:
            self.write_url = kwargs['write_url']
        elif config.has_option('Connection', 'write_url'):
            self.write_url = config.get('Connection', 'write_url')

    def _post(self, data, file_to_upload=None):
        params = {"JSONRPC": simplejson.dumps(data)}
        if file_to_upload:
            from pybrightcove.multipart import MultipartPostHandler
            cookies = cookielib.CookieJar()
            cproc = urllib2.HTTPCookieProcessor(cookies)
            opener = urllib2.build_opener(cproc, MultipartPostHandler)
            params["filePath"] = open(file_to_upload, "rb")
            r = opener.open(self.write_url, params)
            return simplejson.loads(r.read())
        else:
            msg = urllib.urlencode({'json': params['JSONRPC']})
            req = urllib2.urlopen(self.write_url, msg)
            resp = req.read()
            result = simplejson.loads(resp)
            if 'error' in result and result['error']:
                BrightcoveError.raise_exception(data)
            return result['result']

    def _get_response(self, **kwargs):
        url = self.read_url + "?output=JSON&token=%s" % self.read_token
        for key in kwargs:
            if key and kwargs[key]:
                val = kwargs[key]
                if isinstance(val, (list, tuple)):
                    val = ",".join(val)
                url += "&%s=%s" % (key, val)
        req = urllib2.urlopen(url)
        return simplejson.loads(req.read())

    def _base_get_command(self, command, page_size=100, page_number=0,
            sort_by=SortByType.CREATION_DATE, sort_order=SortByOrderType.ASC,
            video_fields=None, get_item_count=True, single=False, **kwargs):
        fields_str = ""
        if video_fields and isinstance(video_fields, (list, tuple)):
            for field in video_fields:
                if field not in PublicVideoFieldsEnum.__dict__.values():
                    raise TypeError('Invalid field value supplied.')
            fields_str = ",".join(video_fields)
        get_item_count_str = "false"
        if get_item_count:
            get_item_count_str = "true"
        data = self._get_response(command=command,
            page_size=page_size, page_number=page_number, sort_by=sort_by,
            sort_order=sort_order, video_fields=fields_str,
            get_item_count=get_item_count_str, **kwargs)
        if 'error' in data:
            BrightcoveError.raise_exception(data)
        if single:
            return Video(data=data)
        return ItemCollection(data=data, collection_type="Video")

    def find_all_videos(self, page_size=100, page_number=0,
            sort_by=SortByType.CREATION_DATE, sort_order=SortByOrderType.ASC,
            video_fields=None, get_item_count=True):
        """
        Find all videos in the Brightcove media library for this account.

        page_size:
            Integer	Number of items returned per page. A page is a subset of
            all of the items that satisfy the request. The maximum page size
            is 100; if you do not set this argument, or if you set it to an
            integer > 100, your results will come back as if you had set
            page_size=100.

        page_number:
            Integer	The zero-indexed number of the page to return.

        sort_by:
            The field by which to sort the results. A SortByType: One of
            PUBLISH_DATE, CREATION_DATE, MODIFIED_DATE, PLAYS_TOTAL,
            PLAYS_TRAILING_WEEK.

        sort_order:
            How to order the results: ascending (ASC) or descending (DESC).

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.

        get_item_count:
            If set to True, return a total_count value with the payload.
        """
        return self._base_get_command(command="find_all_videos",
            page_size=page_size, page_number=page_number, sort_by=sort_by,
            sort_order=sort_order, video_fields=video_fields,
            get_item_count=get_item_count)

    def find_video_by_id(self, video_id, video_fields=None):
        """
        Finds a single video with the specified id.

        video_id
            The id of the video you would like to retrieve.

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.
        """
        return self._base_get_command(command="find_video_by_id",
            video_id=video_id, video_fields=video_fields, single=True)

    def find_related_videos(self, video_id=None, reference_id=None,
            page_size=100, page_number=0, video_fields=None,
            get_item_count=True):
        """
        Finds videos related to the given video. Combines the name and short
        description of the given video and searches for any partial matches in
        the name, description, and tags of all videos in the Brightcove media
        library for this account. More precise ways of finding related videos
        include tagging your videos by subject and using the
        find_videos_by_tags method to find videos that share the same tags: or
        creating a playlist that includes videos that you know are related.

        video_id
            The id of the video we'd like related videos for.

        reference_id
            The publisher-assigned reference id of the video we'd like related
            videos for.

        page_size:
            Integer	Number of items returned per page. A page is a subset of
            all of the items that satisfy the request. The maximum page size
            is 100; if you do not set this argument, or if you set it to an
            integer > 100, your results will come back as if you had set
            page_size=100.

        page_number:
            Integer	The zero-indexed number of the page to return.

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum..

        get_item_count:
            If set to True, return a total_count value with the payload.
        """
        return self._base_get_command(command="find_related_videos",
            video_id=video_id, reference_id=reference_id, page_size=page_size,
            page_number=page_number, video_fields=video_fields,
            get_item_count=get_item_count)

    def find_videos_by_ids(self, video_ids, video_fields=None):
        """
        Find multiple videos, given their ids.

        video_ids
            The list of video ids for the videos we'd like to retrieve.

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.
        """
        return self._base_get_command(command="find_videos_by_ids",
            video_ids=video_ids, video_fields=video_fields)

    def find_video_by_reference_id(self, reference_id, video_fields=None):
        """
        Find a video based on its publisher-assigned reference id.

        reference_id
            The publisher-assigned reference id for the video we're
            searching for.

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.
        """
        return self._base_get_command(command="find_video_by_reference_id",
            reference_id=reference_id, video_fields=video_fields, single=True)

    def find_videos_by_reference_ids(self, reference_ids, video_fields=None):
        """
        Find multiple videos based on their publisher-assigned reference ids.

        reference_ids
            The list of reference ids for the videos we'd like to retrieve

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.
        """
        return self._base_get_command(command="find_videos_by_reference_ids",
            reference_ids=reference_ids, video_fields=video_fields)

    def find_videos_by_user_id(self, user_id, page_size=100, page_number=0,
            sort_by=SortByType.CREATION_DATE, sort_order=SortByOrderType.ASC,
            video_fields=None, get_item_count=True):
        """
        Retrieves the videos uploaded by the specified user id. This method can
        be used to find videos submitted using the consumer-generated media
        (CGM) module.

        user_id
            The id of the user whose videos we'd like to retrieve.

        page_size:
            Integer	Number of items returned per page. A page is a subset of
            all of the items that satisfy the request. The maximum page size
            is 100; if you do not set this argument, or if you set it to an
            integer > 100, your results will come back as if you had set
            page_size=100.

        page_number:
            Integer	The zero-indexed number of the page to return.

        sort_by:
            The field by which to sort the results. A SortByType: One of
            PUBLISH_DATE, CREATION_DATE, MODIFIED_DATE, PLAYS_TOTAL,
            PLAYS_TRAILING_WEEK.

        sort_order:
            How to order the results: ascending (ASC) or descending (DESC).

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.

        get_item_count:
            If set to True, return a total_count value with the payload.
        """
        return self._base_get_command(command="find_videos_by_user_id",
            user_id=user_id, page_size=page_size, page_number=page_number,
            sort_by=sort_by, sort_order=sort_order, video_fields=video_fields,
            get_item_count=get_item_count)

    def find_videos_by_campaign_id(self, campaign_id, page_size=100,
            page_number=0, sort_by=SortByType.CREATION_DATE,
            sort_order=SortByOrderType.ASC, video_fields=None,
            get_item_count=True):
        """
        Gets all the videos associated with the given campaign id. Campaigns
        are a feature of the consumer-generated media (CGM) module

        campaign_id
            The id of the campaign you'd like to fetch videos for.

        page_size:
            Integer	Number of items returned per page. A page is a subset of
            all of the items that satisfy the request. The maximum page size
            is 100; if you do not set this argument, or if you set it to an
            integer > 100, your results will come back as if you had set
            page_size=100.

        page_number:
            Integer	The zero-indexed number of the page to return.

        sort_by:
            The field by which to sort the results. A SortByType: One of
            PUBLISH_DATE, CREATION_DATE, MODIFIED_DATE, PLAYS_TOTAL,
            PLAYS_TRAILING_WEEK.

        sort_order:
            How to order the results: ascending (ASC) or descending (DESC).

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.

        get_item_count:
            If set to True, return a total_count value with the payload.
        """
        return self._base_get_command(command="find_videos_by_campaign_id",
            campaign_id=campaign_id, page_size=page_size,
            page_number=page_number, sort_by=sort_by, sort_order=sort_order,
            video_fields=video_fields, get_item_count=get_item_count)

    def find_videos_by_text(self, text, page_size=100, page_number=0,
        video_fields=None, get_item_count=True):
        """
        Searches through all the videos in this account, and returns a
        collection of videos whose name, short description, or long
        description contain a match for the specified text.

        text
            The text we're searching for.

        page_size:
            Integer Number of items returned per page. A page is a subset of
            all of the items that satisfy the request. The maximum page size
            is 100; if you do not set this argument, or if you set it to an
            integer > 100, your results will come back as if you had set
            page_size=100.

        page_number:
            Integer	The zero-indexed number of the page to return.

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.

        get_item_count:
            If set to True, return a total_count value with the payload.
        """
        return self._base_get_command(command="find_videos_by_text",
            text=text, page_size=page_size, page_number=page_number,
            video_fields=video_fields, get_item_count=get_item_count)

    def find_videos_by_tags(self, and_tags=None, or_tags=None, page_size=100,
            page_number=0, sort_by=SortByType.MODIFIED_DATE,
            sort_order=SortByOrderType.ASC, get_item_count=True,
            video_fields=None):
        """
        Performs a search on all the tags of the videos in this account,
        and returns a collection of videos that contain the specified tags.

        Note that tags are case-sensitive.

        and_tags:
            Limit the results to those that contain all of these tags.

        or_tags
            Limit the results to those that contain at least one of these tags.

        page_size:
            Integer	Number of items returned per page. A page is a subset of
            all of the items that satisfy the request. The maximum page size
            is 100; if you do not set this argument, or if you set it to an
            integer > 100, your results will come back as if you had set
            page_size=100.

        page_number:
            Integer	The zero-indexed number of the page to return.

        sort_by:
            The field by which to sort the results. A SortByType: One of
            PUBLISH_DATE, CREATION_DATE, MODIFIED_DATE, PLAYS_TOTAL,
            PLAYS_TRAILING_WEEK.

        sort_order:
            How to order the results: ascending (ASC) or descending (DESC).

        video_fields:
            List of the fields you wish to have populated in the videos
            contained in the returned object. Passing None populates with all
            fields.  The items in the list should be values from the
            pybrightcove.enums.PublicVideoFieldsEnum enum.

        get_item_count:
            If set to True, return a total_count value with the payload.
        """
        if sort_by not in (SortByType.MODIFIED_DATE,
            SortByType.PLAYS_TRAILING_WEEK):
            raise Exception("Invalid sort by type.")

        return self._base_get_command(command="find_videos_by_tags",
            page_size=page_size, page_number=page_number, sort_by=sort_by,
            sort_order=sort_order, video_fields=video_fields,
            get_item_count=get_item_count, and_tags=and_tags,
            or_tags=or_tags)

    def create_video(self, filename, video, do_checksum=True,
            create_multiple_renditions=True, preserve_source_rendition=True):
        """
        filename:
            The name of hte file that's being uploaded.

        video:
            The metadata for the video you'd like to create.

        create_multiple_renditions:
            If the file is a supported transcodeable type, this optional flag
            can be used to control the number of transcoded renditions.
            If true (default), multiple renditions at varying encoding rates
            and dimensions are created. Setting this to false will cause a
            single transcoded VP6 rendition to be created at the standard
            encoding rate and dimensions.

        preserve_source_rendition:
            If true (default) and if the video file is H.264 encoded and if
            create_multiple_renditions=true, then multiple VP6 renditions are
            created and in addition the H.264 source is retained as an
            additional rendition.
        """
        data = {"method": "create_video"}
        params = {"token": self.write_token}
        params["create_multiple_renditions"] = create_multiple_renditions
        params["create_multiple_renditions"] = preserve_source_rendition
        params["video"] = video.to_dict()
        data["params"] = params

        if do_checksum:
            m = hashlib.md5()
            m.update(open(filename, 'rb').read())
            data['params']['file_checksum'] = m.hexdigest()

        r = self._post(data=data, file_to_upload=filename)
        return r

    def update_video(self, video):
        """
        video:
            The metadata for the video you'd like to update.
        """
        data = {"method": "update_video"}
        params = {"token": self.write_token}
        params["video"] = video.to_dict()
        data['params'] = params
        return Video(data=self._post(data=data))

    def _delete_video(self, video_id, reference_id, cascade, delete_shares):
        data = {'method': 'delete_video'}
        params = {
            'token': self.write_token,
            'cascade': cascade,
            'delete_shares': delete_shares}
        if video_id:
            params['video_id']
        elif reference_id:
            params['reference_id']
        else:
            err_msg = 'You must specify either a video_id or a reference_id'
            raise Exception(err_msg)
        data['params'] = params
        self._post(data=data)

    def delete_video_by_id(self, video_id, cascade=True, delete_shares=True):
        """
        video_id
            The id of the video you'd like to delete

        cascade
            Set this to true if you want to delete this video even if it is
            part of a manual playlist or assigned to a player. The video will
            be removed from all playlists and players in which it appears,
            then deleted.  Defaults to True

        delete_shares
            Set this to true if you want also to delete shared copies of this
            video. Note that this will delete all shared copies from sharee
            accounts, regardless of whether or not those accounts are currently
            using the video in playlists or players. Defaults to True
        """
        self._delete_video(video_id=video_id, reference_id=None,
            cascade=cascade, delete_shares=delete_shares)

    def delete_video_by_reference_id(self, reference_id, cascade=True,
        delete_shares=True):
        """
        reference_id
            The publisher-assigned reference id of the video you'd like to
            delete.

        cascade
            Set this to true if you want to delete this video even if it is
            part of a manual playlist or assigned to a player. The video will
            be removed from all playlists and players in which it appears,
            then deleted.  Defaults to True

        delete_shares
            Set this to true if you want also to delete shared copies of this
            video. Note that this will delete all shared copies from sharee
            accounts, regardless of whether or not those accounts are currently
            using the video in playlists or players. Defaults to True
        """
        self._delete_video(video_id=None, reference_id=reference_id,
            cascade=cascade, delete_shares=delete_shares)
