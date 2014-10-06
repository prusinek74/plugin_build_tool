"""
/***************************************************************************
                                    pb_tool
                 A tool for building and deploying QGIS plugins
                              -------------------
        begin                : 2014-09-24
        copyright            : (C) 2014 by GeoApt LLC
        email                : gsherman@geoapt.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
__author__ = 'gsherman'

import os
import sys
import subprocess
import shutil
import errno
import glob
import ConfigParser
from string import Template
from distutils.dir_util import copy_tree


import click

@click.group()
def cli():
    """Simple Python tool to compile and deploy a QGIS plugin.
    For help on a command use --help after the command:
    pb_tool deploy --help.

    pb_tool requires a configuration file (default: pb_tool.cfg) that
    declares the files and resources used in your plugin. Plugin Builder
    2.6.0 creates a config file when you generate a new plugin template.

    See http://g-sherman.github.io/plugin_build_tool for for an example config
    file. You can also use the create command to generate a best-guess config
    file for an existing project, then tweak as needed."""
    pass


def get_install_files(cfg):
    python_files = cfg.get('files', 'python_files').split()
    main_dialog = cfg.get('files', 'main_dialog').split()
    extras = cfg.get('files', 'extras').split()
    # merge the file lists
    install_files = python_files + main_dialog + compiled_ui(cfg) + compiled_resource(cfg) + extras
    #click.echo(install_files)
    return install_files


@cli.command()
def version():
    """Return the version of pb_tool and exit"""
    click.echo("1.1, 2014-10-04")


@cli.command()
@click.option('--config', default='pb_tool.cfg',
              help='Name of the config file to use if other than pb_tool.cfg')
@click.option('--quick', '-q', is_flag=True,
              help='Do a quick install without compiling ui, resource, docs, \
              and translation files')
def deploy(config, quick):
    """Deploy the plugin to QGIS plugin directory using parameters in pb_tool.cfg"""
    deploy_files(config, quick)


def deploy_files(config, quick):
    """Deploy the plugin using parameters in pb_tool.cfg"""
    # check for the config file
    if not os.path.exists(config):
        click.echo("Configuration file {} is missing.".format(config))
    else:
        cfg = get_config(config)
        plugin_dir = os.path.join(get_plugin_directory(), cfg.get('plugin', 'name'))
        if quick:
            print "Doing quick deployment"
            install_files(plugin_dir, cfg)
            print ("Quick deployment complete---if you have problems with your"
                    " plugin, try doing a full deploy.")
            
            
        else:
            print """Deploying will:
            * Remove your currently deployed version
            * Compile the ui and resource files
            * Build the help docs
            * Copy everything to your .qgis2/python/plugins directory
            """

            if click.confirm("Proceed?"):

                # clean the deployment
                clean_deployment(False, config)
                print "Deploying to {}".format(plugin_dir)
                # compile to make sure everything is fresh
                print 'Compiling to make sure install is clean'
                compile_files(cfg)
                build_docs()
                install_files(plugin_dir, cfg)

def install_files(plugin_dir, cfg):
        errors = []
        install_files = get_install_files(cfg)
        # make the plugin directory if it doesn't exist
        if not os.path.exists(plugin_dir):
            os.mkdir(plugin_dir)

        fail = False
        for file in install_files:
            print ("Copying {}".format(file)),
            try:
                shutil.copy(file, os.path.join(plugin_dir, file))
                print ""
            except Exception as oops:
                errors.append("Error copying files: {}, {}".format(
                    file, oops.strerror))
                print "----> ERROR"
                fail = True
            extra_dirs = cfg.get('files', 'extra_dirs').split()
            #print "EXTRA DIRS: {}".format(extra_dirs)
        for xdir in extra_dirs:
            print "Copying contents of {} to {}".format(xdir, plugin_dir)
            try:
                copy_tree(xdir, "{}/{}".format(plugin_dir, xdir))
            except Exception as oops:
                errors.append("Error copying directory: {}, {}".format(
                    xdir, oops.message))
                fail = True
        help_src = cfg.get('help', 'dir')
        help_target = os.path.join(
            get_plugin_directory(),
            cfg.get('plugin', 'name'),
            cfg.get('help', 'target'))
        print "Copying {} to {}".format(help_src, help_target)
        #shutil.copytree(help_src, help_target)
        try:
            copy_tree(help_src, help_target)
        except Exception as oops:
            errors.append("Error copying help files: {}, {}".format(
                help_src, oops.message))
            fail = True
        if fail:
            print "\nERRORS:"
            for error in errors:
                print error
            print ""
            print "One or more files/directories specified in your config" 
            print  "file failed to deploy---make sure they exist or if not" 
            print  "needed remove them from the config."
            print "To ensure proper deployment, make sure your UI and resource" 
            print "files are compiled. Using dclean to delete"
            print "the plugin before deploying may also help."


def clean_deployment(ask_first=True, config='pb_tool.cfg'):
    """ Remove the deployed plugin from the .qgis2/python/plugins directory
    """
    name = get_config(config).get('plugin', 'name')
    plugin_dir = os.path.join(get_plugin_directory(), name)
    if ask_first:
        proceed = click.confirm('Delete the deployed plugin from {}?'.format(plugin_dir))
    else:
        proceed = True

    if proceed:
        click.echo('Removing plugin from {}'.format(plugin_dir))
        try:
            shutil.rmtree(plugin_dir)
            return True
        except OSError as oops:
            print 'Plugin was not deleted: {}'.format(oops.strerror)
    else:
        click.echo('Plugin was not deleted')
    return False


@cli.command()
def clean_docs():
    """
    Remove the built HTML help files from the build directory
    """
    if os.path.exists('help'):
        click.echo('Removing built HTML from the help documentation')
        if sys.platform == 'win32':
            makeprg = 'make.bat'
        else:
            makeprg = 'make'
        cwd = os.getcwd()
        os.chdir('help')
        subprocess.check_call([makeprg, 'clean'])
        os.chdir(cwd)
    else:
        print "No help directory exists in the current directory"


@cli.command()
@click.option('--config', default='pb_tool.cfg',
              help='Name of the config file to use if other than pb_tool.cfg')
def dclean(config):
    """ Remove the deployed plugin from the .qgis2/python/plugins directory
    """
    clean_deployment(True, config)


@cli.command()
@click.option('--config', default='pb_tool.cfg',
              help='Name of the config file to use if other than pb_tool.cfg')
def clean(config):
    """ Remove compiled resource and ui files
    """
    cfg = get_config(config)
    files = compiled_ui(cfg) + compiled_resource(cfg)
    click.echo('Cleaning resource and ui files')
    for file in files:
        try:
            os.unlink(file)
            print "Deleted: {}".format(file)
        except OSError as oops:
            print "Couldn't delete {}: {}".format(file, oops.strerror)


@cli.command()
@click.option('--config', default='pb_tool.cfg',
              help='Name of the config file to use if other than pb_tool.cfg')
def compile(config):
    """
    Compile the resource and ui files
    """
    compile_files(get_config(config))


@cli.command()
def doc():
    """ Build HTML version of the help files using sphinx"""
    build_docs()


def build_docs():
    """ Build the docs using sphinx"""
    if os.path.exists('help'):
        click.echo('Building the help documentation')
        if sys.platform == 'win32':
            makeprg = 'make.bat'
        else:
            makeprg = 'make'
        cwd = os.getcwd()
        os.chdir('help')
        subprocess.check_call([makeprg, 'html'])
        os.chdir(cwd)
    else:
        print "No help directory exists in the current directory"

@cli.command()
@click.option('--config', default='pb_tool.cfg',
              help='Name of the config file to use if other than pb_tool.cfg')
def translate(config):
    """ Build translations using lrelease. Locales must be specified
    in the config file and the corresponding .ts file must exist in
    the i18n directory of your plugin."""
    # see if we can find the lrelease app
    cmd = check_path('lrelease')
    if not cmd:
        cmd = check_path('lrelease-qt')
    if not cmd:
        print """Unable to find the lrelease command. Make sure it is installed
                 and in your path."""
        if sys.platform == 'win32':
            print ('You can get lrelease by installing'
                    ' the qt4-devel package in the Libs'
                    ' section of the OSGeo4W Advanced Install')
    else:
        cfg = get_config(config)
        if check_cfg(cfg, 'files', 'locales'):
            locales = cfg.get('files', 'locales').split()
            if locales:
                for locale in locales:
                    (name, ext) = os.path.splitext(locale)
                    if ext != '.ts':
                        print 'no ts extension'
                        locale = name + '.ts'
                    print cmd, locale
                    subprocess.check_call([cmd, os.path.join('i18n', locale)])
            else:
                print "No translations are specified in {}".format(config)
                

@cli.command()
@click.option('--config', default='pb_tool.cfg',
              help='Name of the config file to use if other than pb_tool.cfg')
def zip(config):
    """ Package the plugin into a zip file
    suitable for uploading to the QGIS
    plugin repository"""

    name = get_config(config).get('plugin', 'name', None)
    confirm = click.confirm('Do a dclean and deploy first?')
    if confirm:
        clean_deployment(False, config)
        deploy_files(config)

    confirm = click.confirm(
        'Create a packaged plugin ({}.zip) from the deployed files?'.format(name))
    if confirm:
        # delete the zip if it exists
        if os.path.exists('{}.zip'.format(name)):
            os.unlink('{}.zip'.format(name))
        if name:
            cwd = os.getcwd()
            os.chdir(get_plugin_directory())
            subprocess.check_call(['zip', '-r',
                                   os.path.join(cwd, '{}.zip'.format(name)),
                                   name])

            print ('The {}.zip archive has been created in the current directory'.format(name))
        else:
            click.echo("Your config file is missing the plugin name (name=parameter)")


@cli.command()
@click.option('--config', default='pb_tool.cfg',
              help='Name of the config file to use if other than pb_tool.cfg')
def validate(config):
    """
    Check the pb_tool.cfg file for mandatory sections/files
    """
    valid = True
    cfg = get_config(config)
    if not check_cfg(cfg, 'plugin', 'name'):
        valid = False
    if not check_cfg(cfg, 'files', 'python_files'):
        valid = False
    if not check_cfg(cfg, 'files', 'main_dialog'):
        valid = False
    if not check_cfg(cfg, 'files', 'resource_files'):
        valid = False
    if not check_cfg(cfg, 'files', 'extras'):
        valid = False
    if not check_cfg(cfg, 'help', 'dir'):
        valid = False
    if not check_cfg(cfg, 'help', 'target'):
        valid = False

    if valid:
        print "Your {} file is valid and contains all mandatory items".format(config)
    else:
        print "Your {} file is invalid".format(config)


@cli.command()
@click.option('--config', default='pb_tool.cfg',
              help='Name of the config file to use if other than pb_tool.cfg')
def list(config):
    """ List the contents of the configuration file """
    if os.path.exists(config):
        with open(config) as cfg:
            for line in cfg:
                print line[:-1]
    else:
        print "There is no {} file in the current directory".format(config)
        print "We can't do anything without it"


@cli.command()
@click.option('--name', default='pb_tool.cfg',
              help='Name of the config file to create if other than pb_tool.cfg')
def create(name):
    """
    Create a config file based on source files in the current directory
    """
    template = Template(config_template())
    # guess the plugin name
    try:
        metadata = ConfigParser.ConfigParser()
        metadata.read('metadata.txt')
        cfg_name = metadata.get('general', 'name')
    except ConfigParser.NoOptionError as oops:
        print oops.message
    except ConfigParser.NoSectionError as secoops:
        print secoops.message
        #print "Missing section '{}' when looking for option '{}'".format(
        print "Unable to get the name of your plugin from metadata.txt"
        cfg_name = click.prompt("Name of the plugin:")

    # get the list of python files
    py_files = glob.glob('*.py')
    
    # guess the main dialog ui file
    main_dlg = glob.glob('*_dialog_base.ui')

    # get the other ui files
    other_ui = glob.glob('*.ui')
    # remove the main dialog file
    try:
        for ui in main_dlg:
            other_ui.remove(ui)
    except:
        # don't care if we didn't find it
        pass

    # get the resource files (.qrc)
    resources = glob.glob("*.qrc")

    extras = glob.glob('*.png') + glob.glob('metadata.txt')

    locale_list = glob.glob('i18n/*.ts')
    locales = []
    for locale in locale_list:
        locales.append(os.path.basename(locale))


    cfg = template.substitute(Name=cfg_name,
                              PythonFiles=' '.join(py_files),
                              MainDialog=' '.join(main_dlg),
                              CompiledUiFiles=' '.join(other_ui),
                              Resources=' '.join(resources),
                              Extras=' '.join(extras),
                              Locales=' '.join(locales))


    fname = name
    if os.path.exists(fname):
        confirm = click.confirm('{} exists. Overwrite?'.format(name))
        if not confirm:
            fname = click.prompt('Enter a name for the config file:')

    with open(fname, 'w') as f:
        f.write(cfg)

    print "Created new config file in {}".format(fname)


def check_cfg(cfg, section, name):
    try:
        cfg.get(section, name)
        return True
    except ConfigParser.NoOptionError as oops:
        print oops.message
    except ConfigParser.NoSectionError:
        print "Missing section '{}' when looking for option '{}'".format(
              section, name)
    return False


def get_config(config='pb_tool.cfg'):
    """
    Read the config file pb_tools.cfg and return it
    """
    if os.path.exists(config):
        cfg = ConfigParser.ConfigParser()
        cfg.read(config)
        #click.echo(cfg.sections())
        return cfg
    else:
        print "There is no {} file in the current directory".format(config)
        print "We can't do anything without it"
        sys.exit(1)


def compiled_ui(cfg):
    #cfg = get_config(config)
    try:
        uis = cfg.get('files', 'compiled_ui_files').split()
        compiled = []
        for ui in uis:
            (base, ext) = os.path.splitext(ui)
            compiled.append('{}.py'.format(base))
        #print "Compiled UI files: {}".format(compiled)
        return compiled
    except ConfigParser.NoSectionError as oops:
        print oops.message
        sys.exit(1)


def compiled_resource(cfg):
    #cfg = get_config(config)
    try:
        res_files = cfg.get('files', 'resource_files').split()
        compiled = []
        for res in res_files:
            (base, ext) = os.path.splitext(res)
            compiled.append('{}_rc.py'.format(base))
        #print "Compiled resource files: {}".format(compiled)
        return compiled
    except ConfigParser.NoSectionError as oops:
        print oops.message
        sys.exit(1)


def compile_files(cfg):
    # Compile all ui and resource files
    # TODO add changed detection
    #cfg = get_config(config)

    # check to see if we have pyuic4
    pyuic4 = check_path('pyuic4')

    if not pyuic4:
        print "pyuic4 is not in your path---unable to compile your ui files"
    else:
        ui_files = cfg.get('files', 'compiled_ui_files').split()
        ui_count = 0
        for ui in ui_files:
            if os.path.exists(ui):
                (base, ext) = os.path.splitext(ui)
                output = "{}.py".format(base)
                if file_changed(ui, output):
                    print "Compiling {} to {}".format(ui, output)
                    subprocess.check_call([pyuic4, '-o', output, ui])
                    ui_count += 1
                else:
                    print "Skipping {} (unchanged)". format(ui)
            else:
                print "{} does not exist---skipped".format(ui)
        print "Compiled {} UI files".format(ui_count)

    # check to see if we have pyrcc4
    pyrcc4 = check_path('pyrcc4')

    if not pyrcc4:
        print "pyrcc4 is not in your path---unable to compile your resource file(s)"
    else:
        res_files = cfg.get('files', 'resource_files').split()
        res_count = 0
        for res in res_files:
            if os.path.exists(res):
                (base, ext) = os.path.splitext(res)
                output = "{}_rc.py".format(base)
                if file_changed(res, output):
                    print "Compiling {} to {}".format(res, output)
                    subprocess.check_call([pyrcc4, '-o', output, res])
                    res_count += 1
                else:
                    print "Skipping {} (unchanged)". format(res)
            else:
                print "{} does not exist---skipped".format(res)
        print "Compiled {} resource files".format(res_count)


def copy(source, destination):
    """Copy files recursively.

    Taken from: http://www.pythoncentral.io/
                how-to-recursively-copy-a-directory-folder-in-python/

    :param source: Source directory.
    :type source: str

    :param destination: Destination directory.
    :type destination: str

    """
    try:
        #shutil.copytree(source, destination)
        copy_tree(source, destination)
    except OSError as e:
        # If the error was caused because the source wasn't a directory
        if e.errno == errno.ENOTDIR:
            shutil.copy(source, destination)
        else:
            print('Directory not copied. Error: %s' % e)


def get_plugin_directory():
    if sys.platform == 'win32':
        home = os.path.join(os.environ['HOMEDRIVE'], os.environ['HOMEPATH'])
    else:
        home = os.environ['HOME']
    qgis2 = os.path.join('.qgis2', 'python', 'plugins')

    return os.path.join(home, qgis2)


def config_template():
    """
    :return: the template for a pb_tool.cfg file
    """
    template = """# Configuration file for plugin builder tool
# Sane defaults for your plugin generated by the Plugin Builder are
# already set below.
#
# As you add Python source files and UI files to your plugin, add
# them to the appropriate [files] section below.

[plugin]
# Name of the plugin. This is the name of the directory that will
# be created in .qgis2/python/plugins
name: $Name

[files]
# Python  files that should be deployed with the plugin
python_files: $PythonFiles

# The main dialog file that is loaded (not compiled)
main_dialog: $MainDialog

# Other ui files for your dialogs (these will be compiled)
compiled_ui_files: $CompiledUiFiles

# Resource file(s) that will be compiled
resource_files: $Resources

# Other files required for the plugin
extras: $Extras

# Other directories to be deployed with the plugin.
# These must be subdirectories under the plugin directory
extra_dirs:

# ISO code(s) for any locales (translations), separated by spaces.
# Corresponding .ts files must exist in the i18n directory
locales: $Locales

[help]
# the built help directory that should be deployed with the plugin
dir: help/build/html
# the name of the directory to target in the deployed plugin
target: help
"""
    return template

def check_path(app):
    """ Adapted from StackExchange:
        http://stackoverflow.com/questions/377017
    """
    import os
    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    def ext_candidates(fpath):
        yield fpath
        for ext in os.environ.get("PATHEXT", "").split(os.pathsep):
            yield fpath + ext

    fpath, fname = os.path.split(app)
    if fpath:
        if is_exe(app):
            return app
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, app)
            for candidate in ext_candidates(exe_file):
                if is_exe(candidate):
                    return candidate

    return None

def file_changed(infile, outfile):
    try:
        infile_s = os.stat(infile)
        outfile_s = os.stat(outfile)
        return infile_s.st_mtime > outfile_s.st_mtime
    except:
        return True

