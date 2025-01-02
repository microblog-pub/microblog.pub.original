# microblog.pub

A self-hosted, single-user, ActivityPub-powered microblog created by [@tsileo](https://github.com/tsileo/microblog.pub).
This repo and collective is a respectful attempt by the users of the project to keep it going!

[![AGPL 3.0](https://img.shields.io/badge/license-AGPL_3.0-blue.svg?style=flat)](LICENSE)

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md) 

Instances in the wild:

 - [blog.joaocosta.eu](https://blog.joaocosta.eu/)
 - [bw3.dev](https://bw3.dev/)
 - [blog.nigini.me](https://blog.nigini.me)
 - [chrichri.ween.de](https://chrichri.ween.de)
 - [bw3.dev](https://bw3.dev/)


## Features

 - Implements the [ActivityPub](https://activitypub.rocks/) server to server protocol
    - Federate with all the other popular ActivityPub servers like Pleroma, PixelFed, PeerTube, Mastodon...
    - Consume most of the content types available (notes, articles, videos, pictures...)
 - Exposes your ActivityPub profile as a minimalist microblog
    - Author notes in Markdown, with code highlighting support
    - Dedicated section for articles/blog posts (enabled when the first article is posted)
 - Lightweight
    - Uses SQLite, and Python 3.10+
    - Can be deployed on small VPS
 - Privacy-aware
    - EXIF metadata (like GPS location) are stripped before storage
    - Every media is proxied through the server
    - Strict access control for your outbox enforced via HTTP signature
 - **Little** Javascript
    - The UI is mostly pure HTML/CSS
    - Except for tiny bits of hand-written JS
      - or some localized and optional JS libraries to improve usability
 - IndieWeb citizen
    - [IndieAuth](https://www.w3.org/TR/indieauth/) support (OAuth2 extension)
    - [Microformats](http://microformats.org/wiki/Main_Page) everywhere
    - [Micropub](https://www.w3.org/TR/micropub/) support
    - Sends and processes [Webmentions](https://www.w3.org/TR/webmention/)
    - RSS/Atom/[JSON](https://www.jsonfeed.org/) feed
 - Easy to backup
    - Everything is stored in the `data/` directory: config, uploads, secrets, and the SQLite database.

## Getting started

Check out the [online documentation](https://tinyBlogPub.github.io/microblog.pub/)

## Credits

 - Emoji from [Twemoji](https://twemoji.twitter.com/)
 - Awesome custom goose emoji from [@pamela@bsd.network](https://bsd.network/@pamela)


## Contributing

*Development used to take place on [sourcehut](https://sr.ht/~tsileo/microblog.pub/) but is staled for more than a year!*

This is where the project is being reanimated:

 - [ORG](https://github.com/tinyBlogPub/)
 - [CONDUCT](code_of_conduct.md)
 - [CODE](https://github.com/tinyBlogPub/microblog.pub)
    - Contributions are more than welcomed via Pull Requests, but first, make sure to discuss your ideas and get assigned to an issue.
 - [DISCUSSION](https://github.com/tinyBlogPub/microblog.pub/discussions)
    - Where we meet to talk about the project, bounce ideas around, and shape the next steps of the project
 - [ISSUES](https://github.com/tinyBlogPub/microblog.pub/issues)
    - Used for technical description of bugs, issues, and improvements (please use discussion for ideation and open-ended conversations.)

## License

The project is licensed under the [GNU AGPL v3 LICENSE](LICENSE).
