from cbapi.connection import BaseAPI
from cbapi.errors import ApiError
from six import string_types
import logging

log = logging.getLogger(__name__)


class CbTHFeedError(ApiError):
    pass


class InvalidFeedInfo(CbTHFeedError):
    pass


class InvalidReport(CbTHFeedError):
    pass


# TODO(ww): Integrate this with cbapi.NewBaseModel maybe?
# Is there enough similarity between the two?
class FeedBaseModel(object):
    _safe_dict_types = (str, int, float, bool, type(None),)

    def __init__(self, cb):
        super(FeedBaseModel, self).__init__()
        self._cb = cb

    def __str__(self):
        lines = []
        lines.append("{0:s} object, bound to {1:s}.".format(self.__class__.__name__, self._cb.session.server))

        for key, value in self.__dict__.items():
            status = "   "
            # TODO(ww): Don't special-case FeedBaseModel?
            if isinstance(value, FeedBaseModel):
                val = value.__class__.__name__
            else:
                val = str(value)
            if len(val) > 50:
                val = val[:47] + u"..."
            lines.append(u"{0:s} {1:>20s}: {2:s}".format(status, key, val))

        return "\n".join(lines)

    def as_dict(self):
        blob = {}
        for key, value in self.__dict__.items():
            if isinstance(value, self._safe_dict_types):
                blob[key] = value
            elif isinstance(value, list):
                if all(isinstance(x, FeedBaseModel) for x in value):
                    blob[key] = [x.as_dict() for x in value]
                elif all(isinstance(x, self._safe_dict_types) for x in value):
                    blob[key] = value
                else:
                    raise CbTHFeedError("unsupported type for attribute {}: {}".format(key, value.__class__.__name__))
            elif isinstance(value, FeedBaseModel):
                blob[key] = value.as_dict()
            elif isinstance(value, CbThreatHunterFeedAPI):
                continue
            else:
                raise CbTHFeedError("unsupported type for attribute {}: {}".format(key, value.__class__.__name__))
        return blob


class ValidatableModel(FeedBaseModel):
    def validate(self):
        raise CbTHFeedError("validate() not implemented")


class FeedInfo(ValidatableModel):
    """docstring for FeedInfo"""
    def __init__(self, cb, *, name, owner, provider_url, summary, category, access, id=None):
        super(FeedInfo, self).__init__(cb)
        self.name = name
        self.owner = owner
        self.provider_url = provider_url
        self.summary = summary
        self.summary = summary
        self.category = category
        self.access = access
        self.id = id

    def update(self, **kwargs):
        pass

    def delete(self):
        self._cb.delete_feed(self)

    def reports(self):
        resp = self._cb.get_object("/threathunter/feedmgr/v1/feed/{}/report".format(self.id))
        return [Report(self._cb, **report) for report in resp.get("results", [])]

    def replace(self, reports):
        pass


class QueryIOC(FeedBaseModel):
    """docstring for QueryIOC"""
    def __init__(self, cb, *, search_query, index_type=None):
        super(QueryIOC, self).__init__(cb)
        self.search_query = search_query
        self.index_type = index_type


class Report(ValidatableModel):
    """docstring for Report"""
    def __init__(self, cb, *, id, timestamp, title, description, severity, link=None, tags=[], iocs=[], iocs_v2=[], visibility=None):
        super(Report, self).__init__(cb)
        self.id = id
        self.timestamp = timestamp
        self.title = title
        self.description = description
        self.severity = severity
        self.link = link
        self.tags = tags
        self.iocs = iocs
        self.iocs_v2 = iocs_v2
        self.visibility = visibility

    def delete(self):
        # TODO(ww): Pass feed_id in somehow.
        pass


class Feed(ValidatableModel):
    def __init__(self, cb, *, feedinfo, reports):
        super(Feed, self).__init__(cb)
        self.feedinfo = FeedInfo(self._cb, **feedinfo)
        self.reports = [Report(self._cb, **report) for report in reports]

    def delete(self):
        self._cb.delete_feed(self)

    def validate(self):
        self.feedinfo.validate()
        self.reports.validate()


class IOC(ValidatableModel):
    def __init__(self, cb, *, id, match_type, values, field=None, link=None):
        super(IOC, self).__init__(cb)
        self.id = id
        self.match_type = match_type
        self.values = values
        self.field = field
        self.link = link

# class IOCs(object):
#     """docstring for IOCs"""
#     def __init__(self, arg):
#         super(IOCs, self).__init__()
#         self.arg = arg


class CbThreatHunterFeedAPI(BaseAPI):
    """The main entry point into the Cb ThreatHunter PSC Feed API.

    :param str profile: (optional) Use the credentials in the named profile when connecting to the Carbon Black server.
        Uses the profile named 'default' when not specified.

    Usage::

    >>> from cbapi.psc.threathunter import CbThreatHunterFeedAPI
    >>> cb = CbThreatHunterFeedAPI(profile="production")
    """
    def __init__(self, *args, **kwargs):
        super(CbThreatHunterFeedAPI, self).__init__(product_name="psc", *args, **kwargs)
        self._lr_scheduler = None

    def feeds(self, include_public=False):
        resp = self.get_object("/threathunter/feedmgr/v1/feed", query_parameters={"include_public": include_public})
        return [FeedInfo(self, **feed) for feed in resp.get("results", [])]

    def feed(self, feed_id):
        resp = self.get_object("/threathunter/feedmgr/v1/feed/{}".format(feed_id))
        return resp

    def create_feed(self, reports=[], **kwargs):
        feed = Feed(self, feedinfo=kwargs, reports=reports)
        resp = self.post_object("/threathunter/feedmgr/v1/feed", feed.as_dict())
        return FeedInfo(cb, **resp.json())

    def delete_feed(self, feed):
        if isinstance(feed, Feed):
            feed_id = feed.feedinfo.id
        elif isinstance(feed, FeedInfo):
            feed_id = feed.id
        elif isinstance(feed, string_types):
            feed_id = feed
        else:
            raise CbTHFeedError("bad type for feed deletion: {}".format(feed.__class__.__name__))

        self.delete_object("/threathunter/feedmgr/v1/feed/{}".format(feed_id))


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger("cbapi").setLevel(logging.DEBUG)
    logging.getLogger("__main__").setLevel(logging.DEBUG)
    cb = CbThreatHunterFeedAPI()

    feed = cb.create_feed(name="ToB Test Feed", owner="Trail of Bits",
                          provider_url="https://www.trailofbits.com/",
                          summary="A test feed.", category="Partner",
                          access="private")

    feeds = cb.feeds()
    for feed in feeds:
        print(feed)

    cb.delete_feed(feed)
