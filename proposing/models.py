from __future__ import division
import datetime, logging
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.db.models.aggregates import Sum
from django.contrib.auth.models import User
from django.conf import settings
from common.templatetags.filters import slugify
from common.stringify import niceBigInteger
from document.models import Diff
from accounts.models import CustomUser

logger = logging.getLogger(__name__)

class VotablePost(models.Model):
    """ super-model for all votable models """
    creator = models.ForeignKey(CustomUser, related_name="created_proposals", null=True, blank=True)
    create_date = models.DateTimeField(auto_now_add=True)

    @property
    def upvote_score(self):
        v = VotablePost.objects.filter(pk=self.pk).aggregate(Sum('up_down_votes__value'))['up_down_votes__value__sum']
        return v if v else 0 # v is None when no votes have been cast

    def updownvoteFromUser(self, user):
        if not user.is_authenticated():
            return None
        uservotes = self.up_down_votes.filter(user=user)
        if uservotes:
            return uservotes[0]
        return None

    def userCanUpdownvote(self, user):
        if not user.is_authenticated():
            return False
        if self.creator == user:
            return False
        return self.updownvoteFromUser(user) == None

    def userHasUpdownvoted(self, user):
        if not user.is_authenticated():
            return False
        vote = self.updownvoteFromUser(user)
        if vote != None:
            return "up" if vote.value==1 else "down"
        return None

    def hasUpvoted(self, user):
        return self.userHasUpdownvoted(user) == 'up'

    def hasDownvoted(self, user):
        return self.userHasUpdownvoted(user) == 'down'

    def canPressUpvote(self, user):
        return self.userCanUpdownvote(user) or self.userHasUpdownvoted(user) == 'down'

    def canPressDownvote(self, user):
        return self.userCanUpdownvote(user) or self.userHasUpdownvoted(user) == 'up'

    def isEditableBy(self, user):
        if not user.is_authenticated():
            return False
        if self.creator == user:
            return True
        if user.groups.filter(name__iexact="moderators"):
            return True
        return False

    def lastEdit(self):
        return self.edits.latest('id')

class UpDownVote(models.Model):
    user = models.ForeignKey(CustomUser, related_name="up_down_votes")
    post = models.ForeignKey(VotablePost, related_name="up_down_votes")
    date = models.DateTimeField(auto_now=True)
    value = models.IntegerField(choices=((1, 'up'), (-1, 'down')))

class Tag(models.Model):
    name = models.CharField(max_length=35)
    slug = models.SlugField(unique=True)

    def save(self, *args, **kwargs):
        if not self.id:
            # Newly created object, so set slug
            self.slug = slugify(self.name)
        super(Tag, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.name

class VotablePostEdit(models.Model):
    user = models.ForeignKey(CustomUser)
    post = models.ForeignKey(VotablePost, related_name="edits")
    date = models.DateTimeField(auto_now=True)

class ProposalType(models.Model):
    name = models.CharField(max_length=255)
    daysUntilVotingStarts = models.IntegerField("Days until voting starts", default=7)
    minimalUpvotes = models.IntegerField("Minimal upvotes", default=3)
    daysUntilVotingFinishes = models.IntegerField("Days until voting finishes", default=7)
    daysUntilVotingExpires = models.IntegerField("Days until proposal expires", default=60, help_text="Starts from proposal creation date, expiration is due to lack of interest.")

    def __unicode__(self):
        return self.name

class Proposal(VotablePost):
    # constants
    VOTING_STAGE = (
        ('DISCUSSION', 'Discussion'),
        ('VOTING', 'Voting'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    )
    # fields
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    motivation = models.TextField()
    diff = models.ForeignKey(Diff)
    views = models.IntegerField(default=0)
    voting_stage = models.CharField(max_length=20, choices=VOTING_STAGE, default='DISCUSSION')
    voting_date = models.DateTimeField(default=None, null=True, blank=True)
    expire_date = models.DateTimeField(default=None, null=True, blank=True)
    discussion_time = models.IntegerField(default=7)
    tags = models.ManyToManyField(Tag, related_name="proposals")
    avgProposalvoteScore = models.FloatField("score", default=0.0) 
    favorited_by = models.ManyToManyField(User, related_name="favorites", null=True)

    def __unicode__(self):
        return self.title

    @property
    def totalvotescore(self):
        return self.upvote_score + self.proposal_votes.count()

    @property
    def number_of_comments(self):
        return self.comments.count()

    @property
    def finishedVoting(self):
        return self.voting_stage == 'APPROVED' or self.voting_stage == 'REJECTED'

    @property
    def estimatedVotingDate(self):
        if self.voting_stage == 'DISCUSSION':
            nominal_date = self.create_date + datetime.timedelta(days=self.discussion_time)
            return nominal_date if timezone.now() < nominal_date else timezone.now()
        else:
            return self.voting_date

    @property
    def estimatedFinishDate(self):
        return self.estimatedVotingDate + datetime.timedelta(days=settings.VOTING_DAYS) 

    @property
    def expirationDate(self):
        """ date the proposal expires because lack of interest """
        if self.minimalContraintsAreMet():
            return None
        return self.create_date + datetime.timedelta(days=self.discussion_time)

    def minimalNumEndorsementsIsMet(self):
        return self.upvote_score >= settings.MIN_NUM_ENDORSEMENTS_BEFORE_VOTING

    def minimalContraintsAreMet(self):
        """ True if non-date constraints are met """
        return self.minimalNumEndorsementsIsMet()

    @property
    def upvotesNeededBeforeVoting(self):
        """ True if non-date constraints are met """
        missing = settings.MIN_NUM_ENDORSEMENTS_BEFORE_VOTING - self.upvote_score 
        return missing if missing >= 0 else 0
    
    def shouldStartVoting(self):
        # check relevance
        if self.voting_stage != 'DISCUSSION':
            return False
        # should start voting if start properties fullfilled
        shouldStartVoting = (timezone.now() > self.create_date + datetime.timedelta(days=self.discussion_time)
                            and
                            self.minimalContraintsAreMet())
        return shouldStartVoting

    def shouldBeFinished(self):
        # check relevance
        if self.voting_stage != 'VOTING':
            return False
        # should finish voting if end properties fullfilled
        shouldBeFinished = timezone.now() > self.voting_date + datetime.timedelta(days=settings.VOTING_DAYS)
        return shouldBeFinished

    def shouldExpire(self):
        return self.expirationDate and timezone.now() > self.expirationDate

    def save(self, *args, **kwargs):
        if not self.id:
            # Newly created object, so set slug
            self.slug = slugify(self.title)
        super(Proposal, self).save(*args, **kwargs)

    def isValidTitle(self, title):
        """ Check if slug derived from title already exists,
            the title is then automatically also unique.
            Keeps into account possibility of already existing object.
        """
        titleslug = slugify(title)
        try:
            proposal = Proposal.objects.get(slug=titleslug)
            return self.id == proposal.id
            if self.id == proposal.id:
                proposal = Proposal.objects.get(title=title)
                return self.id == proposal.id
            else:
                return False
        except Proposal.DoesNotExist:
            return True

    @property
    def diffWithContext(self):
        return self.diff.getNDiff()

    def addView(self):
        self.views += 1
        self.save()

    def proposalvoteFromUser(self, user):
        if not user.is_authenticated():
            return None
        uservotes = self.proposal_votes.filter(user=user)
        if uservotes:
            return uservotes[0]
        return None

    def userHasProposalvoted(self, user):
        if not user.is_authenticated():
            return None
        vote = self.proposalvoteFromUser(user)
        if vote != None:
            return vote.value
        return None

    def userHasProposalvotedOn(self, user, option):
        return self.userHasProposalvoted(user) == int(option)

    def isApproved(self):
        # QUESTION: should quorum be number of voters of number of votes (c.f.r. liquid democracy, one person can have many votes)
        # Quorum is always number of voters, not number of votes. A quorum is needed to avoid under-the-radar-behaviour.
        return self.avgProposalvoteScore > 0 and self.proposal_votes.count() >= settings.QUORUM_SIZE
    
    def commentsAllowed(self):
        return self.voting_stage == 'DISCUSSION'

    def commentsAllowedBy(self, user):
        return self.commentsAllowed() and (user.is_authenticated() or settings.ANONYMOUS_COMMENTS)

    def isEditableBy(self, user):
        if not super(Proposal, self).isEditableBy(user):
            return False
        return self.proposal in ['DISCUSSION']

    @staticmethod
    def voteOptions():
        """ returns vote options, fit for use in template """
        return [
            ('-5', 'Against'),
            ('-4', ''),
            ('-3', ''),
            ('-2', ''),
            ('-1', ''),
            ('0', 'Neutral'),
            ('1', ''),
            ('2', ''),
            ('3', ''),
            ('4', ''),
            ('5', 'For'),
        ]

    def dateToPx(self, date):
        """ get pixels for timeline in detail.html """
        ## check sanity
        assert self.voting_stage != 'EXPIRED'
        ## get vars
        d10 = datetime.timedelta(days=10)
        begin, voting, finish = self.create_date.date(), self.estimatedVotingDate.date(), self.estimatedFinishDate.date()
        ## get fixed places
        fixed_dateToPx = [
            (begin - d10, -50),
            (begin, 0),
            (voting, 200),
            (finish, 400),
            (finish + d10, 450),
        ]
        ## linear interpolation between fixed dates
        px = fixed_dateToPx[0][1]
        for (date1, px1), (date2, px2) in zip(fixed_dateToPx[:-1], fixed_dateToPx[1:]):
            if date1 < date <= date2:
                px = px1 + (px2-px1)/(date2-date1).days*(date-date1).days
        return px if date < fixed_dateToPx[-1][0] else fixed_dateToPx[-1][1];

    def currentDateToPx(self):
        if self.voting_stage != 'EXPIRED':
            return self.dateToPx(timezone.now().date())
        else:
            return 300

    def expirationDateToPx(self):
        ## check if expiration date is relevant
        if not self.expirationDate:
            return None
        ## only show expiration if it is in the near future (30 days)
        if (self.expirationDate - timezone.now()).days > 30:
            return None
        ## calculate pixels
        return self.dateToPx(self.expirationDate.date())

    def numVotesOn(self, vote_value):
        a = self.final_proxy_proposal_votes.filter(value = vote_value, voted_self=True).aggregate(Sum('numvotes'))
        return a['numvotes__sum'] or 0
    
    def numVotesToPx(self, vote_value):
        max_num_votes = max([self.numVotesOn(i) for i in xrange(-5,6)])
        if max_num_votes==0:
            return 0
        num_votes = self.numVotesOn(int(vote_value))
        fraction = num_votes / max_num_votes
        BAR_HEIGHT = 150 # px
        return fraction * BAR_HEIGHT

    def votesOn(self, vote_value):
        return self.final_proxy_proposal_votes.filter(value = vote_value, voted_self=True)

class Comment(VotablePost):
    # constants
    COMMENT_COLORS = (
        ('POS', 'positive'),
        ('NEUTR', 'neutral'),
        ('NEG', 'negative'),
    )
    # fields
    proposal = models.ForeignKey(Proposal, related_name="comments")
    motivation = models.TextField()
    color = models.CharField(max_length=10, choices=COMMENT_COLORS, default='NEUTR')

    def __unicode__(self):
        return "Comment on {}".format(self.proposal)

    def isEditableBy(self, user):
        if not super(Comment, self).isEditableBy(user):
            return False
        return self.proposal in ['DISCUSSION']

class CommentReply(VotablePost):
    # fields
    comment = models.ForeignKey(Comment, related_name="replies")
    motivation = models.TextField()

    def __unicode__(self):
        return "Reply to comment on {}".format(self.comment.proposal)

    def isEditableBy(self, user):
        if not super(CommentReply, self).isEditableBy(user):
            return False
        return self.comment.proposal in ['DISCUSSION']

"""
    This contains what the user entered on the website for his vote
"""
class ProposalVote(models.Model):
    user = models.ForeignKey(CustomUser, related_name="proposal_votes")
    proposal = models.ForeignKey(Proposal, related_name="proposal_votes")
    date = models.DateTimeField(auto_now=True)
    value = models.IntegerField("The value of the vote")

"""
    This contains where everybodies votes came from 
            and went to
            in effect, it is the voting matrix
            note that if the user_voting did not actually vote, the numvotes need to be interpreted as the number of votes "flowing through" this user, which is an upperbound to what the user would really have if he actually voted.
"""
class ProxyProposalVote(models.Model):
    user_voting = models.ForeignKey(CustomUser, related_name="proxy_proposal_votes")
    user_proxied = models.ForeignKey(CustomUser, related_name="proxied_proposal_votes")
    proposal = models.ForeignKey(Proposal, related_name="proxy_proposal_votes")
    numvotes = models.FloatField(default=0)
    
    @property
    def getUpperBound(self):
        if numvotes>1.0:
            return 1.0
        return numvotes

    @property
    def getVoteOfVotingUser(self):
        return FinalProposalVote.objects.get(proposal=self.proposal, user=self.user_voting)

"""
    This contains who voted what eventually after counting
"""

class FinalProposalVote(models.Model):
    user = models.ForeignKey(CustomUser, related_name="final_proxy_proposal_votes")
    proposal = models.ForeignKey(Proposal, related_name="final_proxy_proposal_votes")
    numvotes = models.FloatField(default=0)
    value = models.FloatField(default=0)
    voted_self = models.BooleanField() #False if this vote actually went to other people

    @property
    def getProxyProposalVoteSources(self):
        return ProxyProposalVote.objects.filter(proposal=self.proposal, user_voting=self.user).all()
 
    @property
    def getProxyProposalVoteEndNodes(self):
        return ProxyProposalVote.objects.filter(proposal=self.proposal, user_proxied=self.user, user_voting__in=self.proposal.proposal_votes.values("user")).all()
'''
    object containing the issued proxies for the voting system
'''
class Proxy(models.Model):
    delegating = models.ForeignKey(CustomUser, related_name="proxies")
    delegates = models.ManyToManyField(CustomUser, related_name="received_proxies")
    tags = models.ManyToManyField(Tag, related_name="allproxies")
    isdefault = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Proxies"
