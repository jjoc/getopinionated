from __future__ import division
import datetime
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.template.defaultfilters import slugify
from common.stringify import niceBigInteger
from document.models import Diff
from accounts.models import CustomUser


class VotablePost(models.Model):
    """ super-model for all votable models """
    creator = models.ForeignKey(CustomUser, related_name="created_proposals", null=True, blank=True)
    create_date = models.DateTimeField(auto_now_add=True)

    @property
    def upvote_score(self):
        num_upvotes = self.up_down_votes.filter(is_up=True).count()
        num_downvotes = self.up_down_votes.filter(is_up=False).count()
        return num_upvotes - num_downvotes

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
            return "up" if vote.is_up else "down"
        return None

    def canPressUpvote(self, user):
        return self.userCanUpdownvote(user) or self.userHasUpdownvoted(user) == 'up'

    def canPressDownvote(self, user):
        return self.userCanUpdownvote(user) or self.userHasUpdownvoted(user) == 'down'

class UpDownVote(models.Model):
    user = models.ForeignKey(CustomUser, related_name="up_down_votes")
    post = models.ForeignKey(VotablePost, related_name="up_down_votes")
    date = models.DateTimeField(auto_now=True)
    is_up = models.BooleanField("True if this is an upvote")

class Tag(models.Model):
    name = models.CharField(max_length=35)
    slug = models.SlugField()

    def save(self, *args, **kwargs):
        if not self.id:
            # Newly created object, so set slug
            self.slug = slugify(self.name)
        super(Tag, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.name

class ProposalType(models.Model):
    name = models.CharField(max_length=255)
    daysUntilVotingStarts = models.IntegerField("Days until voting starts", default=7)
    minimalUpvotes = models.IntegerField("Minimal upvotes", default=3)
    daysUntilVotingFinishes = models.IntegerField("Days until voting finishes", default=7)
    daysUntilVotingExpires = models.IntegerField("Days until proposal expires", default=60, help_text="Starts from proposal creation date, expiration is due to lack of interest.")

    def __unicode__(self):
        return self.name

class Proposal(VotablePost):
    # settings
    VOTING_STAGE = (
        ('DISCUSSION', 'Discussion'),
        ('VOTING', 'Voting'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    )
    # fields
    title = models.CharField(max_length=255)
    slug = models.SlugField()
    motivation = models.TextField()
    diff = models.ForeignKey(Diff)
    views = models.IntegerField(default=0)
    voting_stage = models.CharField(max_length=20, choices=VOTING_STAGE, default='DISCUSSION')
    voting_date = models.DateTimeField(default=None, null=True, blank=True)
    proposal_type = models.ForeignKey(ProposalType)
    tags = models.ManyToManyField(Tag, related_name="proposals")

    def __unicode__(self):
        return self.title

    @property
    def totalvotescore(self):
        return self.upvote_score + self.proposal_votes.count()

    @property
    def number_of_comments(self):
        return self.comments.count()

    @property
    def estimatedVotingDate(self):
        properties = self.proposal_type
        if self.voting_stage == 'DISCUSSION':
            nominal_date = self.create_date + datetime.timedelta(days=properties.daysUntilVotingStarts)
            return nominal_date if timezone.now() < nominal_date else timezone.now()
        else:
            return self.voting_date

    @property
    def estimatedFinishDate(self):
        properties = self.proposal_type
        return self.estimatedVotingDate + datetime.timedelta(days=properties.daysUntilVotingFinishes)

    @property
    def expirationDate(self):
        """ date the proposal expires because lack of interest """
        properties = self.proposal_type
        if self.minimalContraintsAreMet():
            return None
        return self.create_date + datetime.timedelta(days=properties.daysUntilVotingExpires)

    def minimalContraintsAreMet(self):
        """ True if non-date constraints are met """
        properties = self.proposal_type
        return self.upvote_score > properties.minimalUpvotes

    def shouldStartVoting(self):
        # check relevance
        if self.voting_stage != 'DISCUSSION':
            return False
        # should start voting if start properties fullfilled
        properties = self.proposal_type
        shouldStartVoting = (timezone.now() > self.create_date + datetime.timedelta(days=properties.daysUntilVotingStarts)
                            and
                            self.minimalContraintsAreMet())
        return shouldStartVoting

    def shouldBeFinished(self):
        # check relevance
        if self.voting_stage != 'VOTING':
            return False
        # should finish voting if end properties fullfilled
        properties = self.proposal_type
        shouldBeFinished = timezone.now() > self.voting_date + datetime.timedelta(days=properties.daysUntilVotingFinishes)
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
        except Proposal.DoesNotExist:
            return True

    @property
    def diffWithContext(self):
        return self.diff.getNDiff()

    @property
    def proposalvotescore(self):
        total = 0
        for i in xrange(-5,6):
            num_votes = self.proposal_votes.filter(value = i).count()
            total += i*num_votes
        return total

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

    def isAccepted(self):
        return self.proposalvotescore>0

    def initiateVoteCount(self):
        if self.isAccepted():
            ## apply this diff
            try:
                self.diff.fulldocument.getFinalVersion().applyDiff(self.diff)
            except Exception as e:
                print "Error applying diff to final version: ", e
                # TODO: catch this in nice way
            ## convert other proposal diffs
            for proposal in Proposal.objects.filter(
                    ~Q(voting_stage='APPROVED'),
                    ~Q(voting_stage='REJECTED'),
                    ~Q(voting_stage='EXPIRED'),
                    ~Q(pk=self.pk),
                ):
                try:
                    proposal.diff.applyDiffOnThisDiff(self.diff)
                except Exception as e:
                    print "Error applying diff to other diffs: ", e
                    # TODO: catch this in nice way
        else:
            return

    def commentsAllowed(self):
        return self.voting_stage == 'DISCUSSION'

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

class Comment(VotablePost):
    # settings
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

class ProposalVote(models.Model):
    user = models.ForeignKey(CustomUser, related_name="proposal_votes")
    proposal = models.ForeignKey(Proposal, related_name="proposal_votes")
    date = models.DateTimeField(auto_now=True)
    value = models.IntegerField("The value of the vote")

'''
    object containing the issued proxies for the voting system
'''
class Proxy(models.Model):
    delegating = models.ForeignKey(CustomUser, related_name="proxies")
    delegates = models.ManyToManyField(CustomUser, related_name="received_proxies")
    tags = models.ManyToManyField(Tag, related_name="allproxies")

    class Meta:
        verbose_name_plural = "Proxies"
    