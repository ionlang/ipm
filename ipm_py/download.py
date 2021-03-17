import logging
import urllib.request
import urllib.parse
import os
import sys
import shutil
import json

def do_download(args):
    url = urllib.parse.urlparse(args.url)
    if url.netloc and not url.scheme:
        logging.getLogger("ipm-py").error("Missing url scheme")
        exit(1)
    
    if not url.scheme or url.scheme == "file":
        download_file(url.path, args.path)
        logging.getLogger("ipm-py").info("Done.")
    elif url.scheme in ("http", "https", "ftp"):
        download_http(args.url, args.path)
        logging.getLogger("ipm-py").info("Done.")
    elif url.scheme in ("git", "git+git", "git+http", "git+https", "git+ssh", "git+file"):
        if args.url.startswith("git+"):
            url = args.url[4:]
        else:
            url = args.url
        download_git(url, args.path)
        logging.getLogger("ipm-py").info("Done.")
    else:
        logging.getLogger("ipm-py").error("Unsuported url scheme (%s).", url.scheme)
        exit(1)

def download_http(url: str, path_to: str):
    import tempfile
    import mimetypes
    url = urllib.parse.urldefrag(url).url
    mime = mimetypes.MimeTypes()
    mime, encoding = mime.guess_type(url)
    if mime not in ("application/x-tar","application/zip" ):
        logging.getLogger("imp-py").error("Unsuported mime type %s.", mime)
        exit(1)
    filename = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
    with tempfile.NamedTemporaryFile(mode="wb", suffix="_" + filename if filename else None) as tmpf:
        logging.getLogger("imp-py").info("Connecting to %s", urllib.parse.urlsplit(url).hostname)
        with urllib.request.urlopen(url) as response:
            print(response)
            logging.getLogger("imp-py").info("Downloading %s to %s", url, tmpf.name)
            shutil.copyfileobj(response, tmpf)
        download_file(tmpf.name, path_to)


def download_git(url: str, path_to: str):
    git = shutil.which("git")
    if not git:
        logging.getLogger("imp-py").error("Can't find git executable in PATH.")
        exit(1)
    url = urllib.parse.urldefrag(url).url
    url = urllib.parse.urlsplit(url)
    new_path, at, refspec = url.path.rpartition("@")
    if not at:
        new_path, refspec = refspec, None
    url = url._replace(path=new_path).geturl()
    import tempfile
    import subprocess
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run([git, "-c", "advice.detachedHead=off", "clone", "--recursive", "--branch", refspec or "HEAD" , "--depth", "1", "--single-branch", url, tmpdir], check=True)
            download_file(tmpdir, path_to)
    except subprocess.CalledProcessError as e:
        cmd = e.cmd
        if isinstance(cmd, list):
            import shlex
            cmd = shlex.join(cmd)
        logging.getLogger("imp-py").error("Command \"%s\" returned non-zero exit status %d.", cmd, e.returncode)
        exit(1)

files_to_ignore = os.getenv("IPM_IGNORE_FILES", os.pathsep.join([".git", ".gitignore"])).split(os.pathsep)

def download_file(path_from: str, path_to: str):
    path_from = os.path.abspath(path_from)
    if not os.path.exists(path_from):
        logging.getLogger("imp-py").error("%s doesn't exist.", path_from)
        exit(1)
    
    import mimetypes
    mime = mimetypes.MimeTypes()
    mime, encoding = mime.guess_type(path_from)
    if os.path.isdir(path_from):
        if not os.path.isfile(os.path.join(path_from, "package.json")):
            logging.getLogger("imp-py").error("%s doesn't contain a package.json file.", path_from)
            exit(1)
        with open(os.path.join(path_from, "package.json"), "r") as f:
            package_data = json.load(f)
        package_name = "{}-{}".format(package_data["name"], package_data["version"])
        os.makedirs(path_to, exist_ok=True)
        logging.getLogger("imp-py").info("Copying %s to %s", path_from, os.path.join(path_to, package_name))
        shutil.copytree(path_from, os.path.join(path_to, package_name), ignore=(lambda src, names: files_to_ignore))
    elif mime == "application/x-tar":
        import tarfile
        import tempfile
        tar = tarfile.open(path_from, "r:*")
        try:
            info = tar.getmember("./package.json")
        except KeyError:
            logging.getLogger("imp-py").error("%s doesn't contains package.json", path_from)
            exit(1)
        if not info.isfile():
            logging.getLogger("imp-py").error("%s/package.json must be a (regular) file.", path_from)
            exit(1)
        import tempfile
        with tempfile.TemporaryDirectory() as tempdirname:
            tar.extract("./package.json", tempdirname)
            with open(os.path.join(tempdirname, "package.json"), "r") as f:
                package_data = json.load(f)
        if encoding:
            package_name = "{}-{}.tar.{}".format(package_data["name"], package_data["version"], encoding)
        else:
            package_name = "{}-{}.tar".format(package_data["name"], package_data["version"])
        os.makedirs(path_to, exist_ok=True)
        logging.getLogger("imp-py").info("Copying %s to %s", path_from, os.path.join(path_to, package_name))
        shutil.copyfile(path_from, os.path.join(path_to, package_name))
    elif mime == "application/zip":
        import zipfile
        import tempfile
        zip = zipfile.ZipFile(path_from, "r")
        try:
            info = zip.getinfo("package.json")
        except KeyError:
            logging.getLogger("imp-py").error("%s doesn't contains package.json", path_from)
            exit(1)
        if info.is_dir():
            logging.getLogger("imp-py").error("%s/package.json must be a file.", path_from)
            exit(1)
        with tempfile.TemporaryDirectory() as tempdirname:
            zip.extract("package.json", tempdirname)
            with open(os.path.join(tempdirname, "package.json"), "r") as f:
                package_data = json.load(f)
        package_name = "{}-{}.zip".format(package_data["name"], package_data["version"])
        os.makedirs(path_to, exist_ok=True)
        logging.getLogger("imp-py").info("Copying %s to %s", path_from, os.path.join(path_to, package_name))
        shutil.copyfile(path_from, os.path.join(path_to, package_name))
