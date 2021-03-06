#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime
from django.conf import settings
from django.http import Http404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, get_object_or_404
from zds.gallery.forms import ImageForm, GalleryForm, UserGalleryForm, ImageAsAvatarForm
from zds.gallery.models import UserGallery, Image, Gallery
from zds.member.decorator import can_write_and_read_now
from zds.utils import render_template
from zds.utils import slugify



@login_required
def gallery_list(request):
    """Display the gallery list with all their images."""

    galleries = UserGallery.objects.all().filter(user=request.user)
    return render_template("gallery/gallery/list.html",
                           {"galleries": galleries})



@login_required
def gallery_details(request, gal_pk, gal_slug):
    """Gallery details."""

    gal = get_object_or_404(Gallery, pk=gal_pk)
    try:
        gal_mode = UserGallery.objects.get(gallery=gal, user=request.user)
    except:
        raise PermissionDenied
    images = gal.get_images()
    form = UserGalleryForm()

    return render_template("gallery/gallery/details.html", {
        "gallery": gal,
        "gallery_mode": gal_mode,
        "images": images,
        "form": form,
    })


@can_write_and_read_now
@login_required
def new_gallery(request):
    """Creates a new gallery."""

    if request.method == "POST":
        form = GalleryForm(request.POST)
        if form.is_valid():
            data = form.data

            # Creating the gallery

            gal = Gallery()
            gal.title = data["title"]
            gal.subtitle = data["subtitle"]
            gal.slug = slugify(data["title"])
            gal.pubdate = datetime.now()
            gal.save()

            # Attach user

            userg = UserGallery()
            userg.gallery = gal
            userg.mode = "W"
            userg.user = request.user
            userg.save()
            return redirect(gal.get_absolute_url())
        else:
            return render_template("gallery/gallery/new.html", {"form": form})
    else:
        form = GalleryForm()
        return render_template("gallery/gallery/new.html", {"form": form})


@can_write_and_read_now
@require_POST
@login_required
def modify_gallery(request):
    """Modify gallery instance."""

    # Global actions

    if "delete_multi" in request.POST:
        l = request.POST.getlist("items")
        perms = UserGallery.objects.filter(gallery__pk__in=l,
                                           user=request.user, mode="W").count()

        # Check that the user has the RW right on each gallery

        if perms < len(l):
            raise PermissionDenied

        # Delete all the permissions on all the selected galleries

        UserGallery.objects.filter(gallery__pk__in=l).delete()

        # Delete all the images of the gallery (autodelete of file)

        Image.objects.filter(gallery__pk__in=l).delete()

        # Finally delete the selected galleries

        Gallery.objects.filter(pk__in=l).delete()
        return redirect(reverse("zds.gallery.views.gallery_list"))
    elif "adduser" in request.POST:

        # Gallery-specific actions

        try:
            gal_pk = request.POST["gallery"]
        except KeyError:
            raise Http404
        gallery = get_object_or_404(Gallery, pk=gal_pk)

        # Disallow actions to read-only members

        try:
            gal_mode = UserGallery.objects.get(gallery=gallery,
                                               user=request.user)
            if gal_mode.mode != "W":
                raise PermissionDenied
        except:
            raise PermissionDenied
        form = UserGalleryForm(request.POST)
        if form.is_valid():
            user = get_object_or_404(User, username=request.POST["user"])

            # If a user is already in a user gallery, we don't add him.

            galleries = UserGallery.objects.filter(gallery=gallery,
                                                   user=user).all()
            if galleries.count() > 0:
                return redirect(gallery.get_absolute_url())
            ug = UserGallery()
            ug.user = user
            ug.gallery = gallery
            ug.mode = request.POST["mode"]
            ug.save()
        else:
            return render_template("gallery/gallery/details.html", {
                "gallery": gallery,
                "gallery_mode": gal_mode,
                "images": gallery.get_images(),
                "form": form,
            })
    return redirect(gallery.get_absolute_url())


@login_required
def edit_image(request, gal_pk, img_pk):
    """Creates a new image."""

    gal = get_object_or_404(Gallery, pk=gal_pk)
    img = get_object_or_404(Image, pk=img_pk)

    # check if user can edit image
    try:
        permission = UserGallery.objects.get(user=request.user, gallery=gal)
        if permission.mode != 'W':
            raise PermissionDenied
    except:
        raise PermissionDenied

    # check if the image belong to the gallery
    if img.gallery != gal:
        raise PermissionDenied

    if request.method == "POST":
        form = ImageForm(request.POST, request.FILES)
        if form.is_valid() and request.FILES["physical"].size < settings.IMAGE_MAX_SIZE:
            img.title = request.POST["title"]
            img.legend = request.POST["legend"]
            img.physical = request.FILES["physical"]
            img.slug = slugify(request.FILES["physical"])
            img.update = datetime.now()
            img.save()

            # Redirect to the document list after POST
            return redirect(gal.get_absolute_url())
    else:
        form = ImageForm(initial={"title": img.title, "legend": img.legend, "physical": img.physical})

    as_avatar_form = ImageAsAvatarForm()
    return render_template(
        "gallery/image/edit.html", {
            "form": form,
            "as_avatar_form": as_avatar_form,
            "gallery": gal,
            "image": img
        })


@can_write_and_read_now
@login_required
def modify_image(request):

    # We only handle secured POST actions

    if request.method != "POST":
        raise Http404
    try:
        gal_pk = request.POST["gallery"]
    except KeyError:
        raise Http404
    gal = get_object_or_404(Gallery, pk=gal_pk)
    try:
        gal_mode = UserGallery.objects.get(gallery=gal, user=request.user)

        # Only allow RW users to modify images

        if gal_mode.mode != "W":
            raise PermissionDenied
    except:
        raise PermissionDenied
    if "delete" in request.POST:
        try:
            img = Image.objects.get(pk=request.POST["image"], gallery=gal)
            img.delete()
        except:
            pass
    elif "delete_multi" in request.POST:
        l = request.POST.getlist("items")
        Image.objects.filter(pk__in=l, gallery=gal).delete()
    return redirect(gal.get_absolute_url())


@can_write_and_read_now
@login_required
def new_image(request, gal_pk):
    """Creates a new image."""

    gal = get_object_or_404(Gallery, pk=gal_pk)

    # check if the user can upload new image in this gallery
    try:
        gal_mode = UserGallery.objects.get(gallery=gal, user=request.user)
        if gal_mode.mode != 'W':
            raise PermissionDenied
    except:
        raise PermissionDenied

    if request.method == "POST":
        form = ImageForm(request.POST, request.FILES)
        if form.is_valid() and request.FILES["physical"].size \
                < settings.IMAGE_MAX_SIZE:
            img = Image()
            img.physical = request.FILES["physical"]
            img.gallery = gal
            img.title = request.POST["title"]
            img.slug = slugify(request.FILES["physical"])
            img.legend = request.POST["legend"]
            img.pubdate = datetime.now()
            img.save()

            # Redirect to the newly uploaded image edit page after POST

            return redirect(reverse("zds.gallery.views.edit_image",
                                    args=[gal.pk, img.pk]))
        else:
            return render_template("gallery/image/new.html", {"form": form,
                                                              "gallery": gal})
    else:
        form = ImageForm()  # A empty, unbound form
        return render_template("gallery/image/new.html", {"form": form,
                                                          "gallery": gal})
