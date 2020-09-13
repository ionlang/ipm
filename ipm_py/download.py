import logging
import urllib.request
import urllib.parse
import os
import sys
import shutil
import json
import tempfile
import subprocess
import stat
import shlex
import mimetypes
import tarfile
import zipfile


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
    url = urllib.parse.urldefrag(url).url
    mime = mimetypes.MimeTypes()
    mime, encoding = mime.guess_type(url)
    if mime not in ("application/x-tar", "application/zip"):
        logging.getLogger("imp-py").error("Unsuported mime type %s.", mime)
        exit(1)

    filename = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
    with tempfile.NamedTemporaryFile(mode="wb", suffix="_" + filename if filename else None) as tmpf:
        logging.getLogger("imp-py").info("Connecting to %s", urllib.parse.urlsplit(url).hostname)
        with urllib.request.urlopen(url) as response:
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
    filename = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
    if filename.endswith(".git"):
        filename = filename[:-4]
    try:
        with tempfile.TemporaryDirectory(suffix="_" + filename if filename else None) as tmpdir:
            subprocess.run([git, "init", tmpdir], check=True)
            subprocess.run([git, "pull", "--depth=1", url, refspec or "HEAD"], cwd=tmpdir, check=True)
            if not os.path.isfile(os.path.join(tmpdir, "package.json")):
                logging.getLogger("imp-py").error("%s doesn't contain a package.json file.", tmpdir)
                exit(1)
            subprocess.run([git, "submodule", "update", "--init", "--recursive", "--depth=1"], cwd=tmpdir, check=True)
            result = subprocess.run([git, "submodule", "status", "--recursive"], cwd=tmpdir, check=True, text=True, capture_output=True)

            for path in (x.split()[1] for x in result.stdout.splitlines()):
                os.unlink(os.path.join(tmpdir, path, ".git"))
            def onerror(func, path, exc_info):
                os.chmod(path, stat.S_IWRITE)
                os.unlink(path)
            shutil.rmtree(os.path.join(tmpdir, ".git"), onerror=onerror)
            download_file(tmpdir, path_to)
    except subprocess.CalledProcessError as e:
        cmd = e.cmd
        if isinstance(cmd, list):
            cmd = shlex.join(cmd)
        logging.getLogger("imp-py").error("Command \"%s\" returned non-zero exit status %d.", cmd, e.returncode)
        exit(1)


def download_file(path_from: str, path_to: str):
    path_from = os.path.abspath(path_from)
    if not os.path.exists(path_from):
        logging.getLogger("imp-py").error("%s doesn't exist.", path_from)
        exit(1)

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
        shutil.copytree(path_from, os.path.join(path_to, package_name))
    elif mime == "application/x-tar":
        tar = tarfile.open(path_from, "r:*")
        try:
            info = tar.getmember("./package.json")
        except KeyError:
            logging.getLogger("imp-py").error("%s doesn't contains package.json", path_from)
            exit(1)
        if not info.isfile():
            logging.getLogger("imp-py").error("%s/package.json must be a (regular) file.", path_from)
            exit(1)
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
