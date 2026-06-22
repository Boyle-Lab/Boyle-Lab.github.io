---
layout: post
status: publish
title: Congratulations Dr. Van Deynze!
date: '2025-10-06'
external-url:
teaser: 2025/INSERT_PHOTO_PATH
categories:
- Students
---

Kinsey completed her Ph.D. defense today! She will be continuing on with a Postdoc at The University of Michigan! 
<br>
Congrats! 

<div>
{% for image in site.static_files %}
    {% if image.path contains '2025-10-06-Breanna_PhD' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
