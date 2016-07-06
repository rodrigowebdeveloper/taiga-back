# -*- coding: utf-8 -*-
# Copyright (C) 2014-2016 Andrey Antukh <niwi@niwi.nz>
# Copyright (C) 2014-2016 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014-2016 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2014-2016 Alejandro Alonso <alejandro.alonso@kaleidos.net>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.utils.translation import ugettext as _

from taiga.base.api import serializers
from taiga.base.api import validators
from taiga.base.api.utils import get_object_or_404
from taiga.base.exceptions import ValidationError
from taiga.base.fields import PgArrayField
from taiga.base.fields import PickledObjectField
from taiga.projects.milestones.validators import MilestoneExistsValidator
from taiga.projects.models import Project
from taiga.projects.notifications.mixins import EditableWatchedResourceSerializer
from taiga.projects.notifications.validators import WatchersValidator
from taiga.projects.tagging.fields import TagsAndTagsColorsField
from taiga.projects.validators import ProjectExistsValidator, UserStoryStatusExistsValidator

from . import models

import json


class UserStoryExistsValidator:
    def validate_us_id(self, attrs, source):
        value = attrs[source]
        if not models.UserStory.objects.filter(pk=value).exists():
            msg = _("There's no user story with that id")
            raise ValidationError(msg)
        return attrs


class RolePointsField(serializers.WritableField):
    def to_native(self, obj):
        return {str(o.role.id): o.points.id for o in obj.all()}

    def from_native(self, obj):
        if isinstance(obj, dict):
            return obj
        return json.loads(obj)


class UserStoryValidator(WatchersValidator, EditableWatchedResourceSerializer, validators.ModelValidator):
    tags = TagsAndTagsColorsField(default=[], required=False)
    external_reference = PgArrayField(required=False)
    points = RolePointsField(source="role_points", required=False)
    tribe_gig = PickledObjectField(required=False)

    class Meta:
        model = models.UserStory
        depth = 0
        read_only_fields = ('created_date', 'modified_date', 'owner')


class UserStoriesBulkValidator(ProjectExistsValidator, UserStoryStatusExistsValidator,
                               validators.Validator):
    project_id = serializers.IntegerField()
    status_id = serializers.IntegerField(required=False)
    bulk_stories = serializers.CharField()


# Order bulk validators

class _UserStoryOrderBulkValidator(UserStoryExistsValidator, validators.Validator):
    us_id = serializers.IntegerField()
    order = serializers.IntegerField()


class UpdateUserStoriesOrderBulkValidator(ProjectExistsValidator, UserStoryStatusExistsValidator,
                                          validators.Validator):
    project_id = serializers.IntegerField()
    bulk_stories = _UserStoryOrderBulkValidator(many=True)


# Milestone bulk validators

class _UserStoryMilestoneBulkValidator(UserStoryExistsValidator, validators.Validator):
    us_id = serializers.IntegerField()


class UpdateMilestoneBulkValidator(ProjectExistsValidator, MilestoneExistsValidator, validators.Validator):
    project_id = serializers.IntegerField()
    milestone_id = serializers.IntegerField()
    bulk_stories = _UserStoryMilestoneBulkValidator(many=True)

    def validate(self, data):
        """
        All the userstories and the milestone are from the same project
        """
        user_story_ids = [us["us_id"] for us in data["bulk_stories"]]
        project = get_object_or_404(Project, pk=data["project_id"])

        if project.user_stories.filter(id__in=user_story_ids).count() != len(user_story_ids):
            raise ValidationError("all the user stories must be from the same project")

        if project.milestones.filter(id=data["milestone_id"]).count() != 1:
            raise ValidationError("the milestone isn't valid for the project")

        return data
