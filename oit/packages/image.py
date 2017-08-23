import yaml
import shutil
import os

from common import assert_file, assert_exec, assert_dir, Dir, recursive_overwrite
from model import Model, Missing


class ImageMetadata(object):

    def __init__(self, runtime, dir, name):
        self.runtime = runtime
        self.dir = os.path.abspath(dir)
        self.config_path = os.path.join(self.dir, "config.yml")
        self.name = name

        runtime.verbose("Loading image metadata for %s from %s" % (name, self.config_path))

        assert_file(self.config_path, "Unable to find image configuration file")

        # Create an array of lines to eliminate the possibility of linefeed differences
        config_yml_lines = list(runtime.global_yaml_lines)
        with open(self.config_path, "r") as f:
            for line in f.readlines():
                config_yml_lines.append(line.rstrip())

        config_yml_content = "\n".join(config_yml_lines)
        runtime.verbose(config_yml_content)
        self.config = Model(yaml.load(config_yml_content))

        self.type = "rpms"  # default type is rpms
        if self.config.repo.type is not Missing:
            self.type = self.config.repo.type

        self.qualified_name = "%s/%s" % (self.type, name)

        self.distgit_dir = None

    def clone_distgit(self):
        with Dir(self.runtime.distgits_dir):
            cmd_list = ["rhpkg"]

            if self.runtime.user is not None:
                cmd_list.append("--user=%s" % self.runtime.user)

            cmd_list.extend(["clone", self.qualified_name])

            self.distgit_dir = os.path.abspath(os.path.join(os.getcwd(), self.name))

            self.runtime.info("Cloning distgit repository: %s" % self.qualified_name, self.distgit_dir)

            # Clone the distgit repository
            assert_exec(self.runtime, cmd_list)

            with Dir(self.distgit_dir):
                # Switch to the target branch
                assert_exec(self.runtime, ["rhpkg", "switch-branch", self.runtime.distgit_branch])

    def source_path(self):
        """
        :return: Returns the directory containing the source which should be used to populate distgit.
        """
        alias = self.config.content.source.alias

        # TODO: enable source to be something other than an alias?
        #       A fixed git URL and branch for example?
        if alias is Missing:
            raise IOError("Can't find source alias in image config: %s" % self.dir)

        if alias not in self.runtime.source_alias:
            raise IOError("Required source alias has not been registered [%s] for image config: %s" % (alias, self.dir))

        source_root = self.runtime.source_alias[alias]
        sub_path = self.config.content.source.path

        path = source_root
        if sub_path is not Missing:
            path = os.path.join(source_root, sub_path)

        assert_dir(path, "Unable to find path within source [%s] for config: %s" % (path, self.dir))
        return path

    def populate_distgit_dir(self):

        with Dir(self.distgit_dir):

            # If content.source is defined, pull in content from local source directory
            if self.config.content.source is not Missing:

                # Clean up any files not special to the distgit repo
                for ent in os.listdir("."):

                    # Do not delete anything that is hidden
                    # protects .oit, .gitignore, others
                    if ent.startswith("."):
                        continue

                    # Skip special files that aren't hidden
                    if ent in ["additional-tags"]:
                        continue

                    # Otherwise, clean up the entry
                    shutil.rmtree(ent)

                # Copy all files and overwrite where necessary
                recursive_overwrite(self.source_path(), self.distgit_dir)

                # See if the config is telling us a file other than "Dockerfile" defines the
                # distgit image content.
                dockerfile_name = self.config.content.source.dockerfile
                if dockerfile_name is not Missing and dockerfile_name != "Dockerfile":

                    # Does a non-distgit Dockerfile already exists from copying source; remove if so
                    if os.path.isfile("Dockerfile"):
                        os.remove("Dockerfile")

                    # Rename our distgit source Dockerfile appropriately
                    os.rename(dockerfile_name, "Dockerilfe")

                # Clean up any extraneous Dockerfile.* that might be distractions (e.g. Dockerfile.centos)
                for ent in os.listdir("."):
                    if __name__ == '__main__':
                        if ent.startswith("Dockerfile."):
                            os.remove(ent)

            # In any case, we need to update things like version, release, FROM, etc.


