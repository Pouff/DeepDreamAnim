#!/usr/bin/python
__author__ = 'Samim.io'

# Imports
import argparse
import time
import os
import errno
import subprocess
#import natsort

from cStringIO import StringIO
import numpy as np
import scipy.ndimage as nd
import PIL.Image
from google.protobuf import text_format
import caffe

# a couple of utility functions for converting to and from Caffe's input image layout
def preprocess(net, img):
    return np.float32(np.rollaxis(img, 2)[::-1]) - net.transformer.mean['data']


def deprocess(net, img):
    return np.dstack((img + net.transformer.mean['data'])[::-1])


def objective_L2(dst):
    dst.diff[:] = dst.data


# First we implement a basic gradient ascent step function, applying the first two tricks // 32:
def make_step(net, step_size=1.5, end='inception_4c/output', jitter=32, clip=True, objective=objective_L2):
    '''Basic gradient ascent step.'''

    src = net.blobs['data']  # input image is stored in Net's 'data' blob
    dst = net.blobs[end]

    ox, oy = np.random.randint(-jitter, jitter + 1, 2)
    src.data[0] = np.roll(np.roll(src.data[0], ox, -1), oy, -2)  # apply jitter shift

    net.forward(end=end)
    objective(dst)  # specify the optimization objective
    net.backward(start=end)
    g = src.diff[0]
    # apply normalized ascent step to the input image
    src.data[:] += step_size / np.abs(g).mean() * g
    src.data[0] = np.roll(np.roll(src.data[0], -ox, -1), -oy, -2)  # unshift image

    if clip:
        bias = net.transformer.mean['data']
        src.data[:] = np.clip(src.data, -bias, 255 - bias)


def deepdream(net, base_img, iter_n=10, octave_n=4, step_size=1.5, octave_scale=1.4, jitter=32,
              end='inception_4c/output', clip=True, **step_params):
    # prepare base images for all octaves
    octaves = [preprocess(net, base_img)]
    for i in xrange(octave_n - 1):
        octaves.append(nd.zoom(octaves[-1], (1, 1.0 / octave_scale, 1.0 / octave_scale), order=1))

    src = net.blobs['data']
    detail = np.zeros_like(octaves[-1])  # allocate image for network-produced details
    for octave, octave_base in enumerate(octaves[::-1]):
        h, w = octave_base.shape[-2:]
        if octave > 0:
            # upscale details from the previous octave
            h1, w1 = detail.shape[-2:]
            detail = nd.zoom(detail, (1, 1.0 * h / h1, 1.0 * w / w1), order=1)

        src.reshape(1, 3, h, w)  # resize the network's input image size
        src.data[0] = octave_base + detail
        for i in xrange(iter_n):
            make_step(net, end=end, step_size=step_size, jitter=jitter, clip=clip, **step_params)

            # visualization
            vis = deprocess(net, src.data[0])
            if not clip:  # adjust image contrast if clipping is disabled
                vis = vis * (255.0 / np.percentile(vis, 99.98))
            print octave, i, end, vis.shape

        # extract details produced on the current octave
        detail = src.data[0] - octave_base
    # returning the resulting image
    return deprocess(net, src.data[0])


# Animaton functions

def resizePicture(image, width):
    img = PIL.Image.open(image)
    basewidth = width
    wpercent = (basewidth / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    return img.resize((basewidth, hsize), PIL.Image.ANTIALIAS)


def morphPicture(filename1, filename2, blend, width):
    img1 = PIL.Image.open(filename1)
    img2 = PIL.Image.open(filename2)
    if width is not 0:
        img2 = resizePicture(filename2, width)
    return PIL.Image.blend(img1, img2, blend)


def make_sure_path_exists(path):
    # make sure input and output directory exist, if not create them. If another error (permission denied) throw an error.
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def main(inputdir, outputdir, preview, octaves, octave_scale, iterations, jitter, zoom, stepsize, blend, layers, guide,
         gpu, flow, binocular):
    # input var setup
    make_sure_path_exists(inputdir)
    make_sure_path_exists(outputdir)
    if preview is None: preview = 0
    if octaves is None: octaves = 4
    if octave_scale is None: octave_scale = 1.5
    if iterations is None: iterations = 10
    if jitter is None: jitter = 32
    if jitter is None: jitter = 32
    if zoom is None: zoom = 1
    if stepsize is None: stepsize = 1.5
    if blend is None: blend = 0.5
    if layers is None: layers = ['inception_4c/output']
    if gpu is None: gpu = 1
    if flow is None: flow = 0
    if binocular is None:
        binocular = 0
    else if binocular != 0:
        assert(flow != 0) # currently binocular and optic flow are meant to work together
    # net.blobs.keys()

    # Loading DNN model
    model_name = 'bvlc_googlenet'
    model_path = os.path.join('../../caffe/models/', model_name)
    net_fn = os.path.join(model_path, 'deploy.prototxt')
    param_fn = os.path.join(model_path, 'bvlc_googlenet.caffemodel')

    # Patching model to be able to compute gradients.
    # Note that you can also manually add "force_backward: true" line to "deploy.prototxt".
    model = caffe.io.caffe_pb2.NetParameter()
    text_format.Merge(open(net_fn).read(), model)
    model.force_backward = True
    open('tmp.prototxt', 'w').write(str(model))

    net = caffe.Classifier('tmp.prototxt', param_fn,
                           mean=np.float32([104.0, 116.0, 122.0]),  # ImageNet mean, training set dependent
                           channel_swap=(2, 1, 0))  # the reference model has channels in BGR order instead of RGB

    if gpu is 1:
        caffe.set_mode_gpu()
        caffe.set_device(0)

    # load images & sort them
    if binocular = 1:
        vidinput_left  = os.listdir(os.path.join(inputdir, 'Left'))
        vidinput_right = os.listdir(os.path.join(inputdir, 'Right'))
        vids = [[],[]]
        for frame in vidinput_left:
            if not ".png" in frame: continue
            vids[0].append(frame)
        for frame in vidinput_right:
            if not ".png" in frame: continue
            vids[1].append(frame)
        assert(len(vids[0]) == len(vids[1]), 'Left and right videos must have same number of frames')
        frame0 = vids[0][0]
        numframe = len(vids[0])
    else:
        vidinput = os.listdir(inputdir)
        #vidinput = natsort.natsorted(os.listdir(inputdir))
        vids = []
        # create list
        for frame in vidinput:
            if not ".png" in frame: continue
            vids.append(frame)
        frame0 = vids[0]
        numframe = len(vids)

    var_counter = 1

    img = PIL.Image.open(os.path.join(inputdir, frame0))
    if preview is not 0:
        img = resizePicture(os.path.join(inputdir, frame0), preview)
    frame = np.float32(img)

    # guide
    if guide is not None:
        guideimg = PIL.Image.open(os.path.join(inputdir, guide))
        guideimgresized = guideimg.resize((224, 224), PIL.Image.ANTIALIAS)
        guide = np.float32(guideimgresized)
        end = layers[0]  # 'inception_3b/output'
        h, w = guide.shape[:2]
        src, dst = net.blobs['data'], net.blobs[end]
        src.reshape(1, 3, h, w)
        src.data[0] = preprocess(net, guide)
        net.forward(end=end)
        guide_features = dst.data[0].copy()

    def objective_guide(dst):
        x = dst.data[0].copy()
        y = guide_features
        ch = x.shape[0]
        x = x.reshape(ch, -1)
        y = y.reshape(ch, -1)
        A = x.T.dot(y)  # compute the matrix of dot-products with guide features
        dst.diff[0].reshape(ch, -1)[:] = y[:, A.argmax(1)]  # select ones that match best

    def getFrame(net, frame, endparam):
        # dream frame
        if guide is None:
            return deepdream(net, frame, iter_n=iterations, step_size=stepsize, octave_n=octaves,
                             octave_scale=octave_scale, jitter=jitter, end=endparam)
        else:
            return deepdream(net, frame, iter_n=iterations, step_size=stepsize, octave_n=octaves,
                             octave_scale=octave_scale, jitter=jitter, end=endparam, objective=objective_guide)

    def getStats(saveframe, var_counter, numframe, difference):
        # Stats
        print '***************************************'
        print 'Saving Image As: ' + saveframe
        print 'Frame ' + str(var_counter) + ' of ' + str(numframe)
        print 'Frame Time: ' + str(difference) + 's'
        timeleft = difference * (numframe - var_counter)
        m, s = divmod(timeleft, 60)
        h, m = divmod(m, 60)
        print 'Estimated Total Time Remaining: ' + str(timeleft) + 's (' + "%d:%02d:%02d" % (h, m, s) + ')'
        print '***************************************'

    if flow is 1:
        import cv2

        # optical flow
        if binocular == 1:
            imgLeft = np.float32(PIL.Image.open(os.path.join(inputdir, 'Left', frame0)))
            h, w, c = imgLeft.shape
            halluLeft = getFrame(net, imgLeft, layers[0])
            np.clip(halluLeft, 0, 255, out=halluLeft)
            PIL.Image.fromarray(np.uint8(halluLeft)).save(os.path.join(outputdir, 'Left', 'frame_000000.png'))
            grayImgLeft = cv2.cvtColor(imgLeft, cv2.COLOR_RGB2GRAY)

            imgRight = np.float32(PIL.Image.open(os.path.join(inputdir, 'Right', vids[1][0])))
            grayImgRight = cv2.cvtColor(imgRight, cv2.COLOR_RGB2GRAY)
            flow = cv2.calcOpticalFlowFarneback(grayImgLeft, grayImgRight, pyr_scale=0.5, levels=3, winsize=15,
                                                iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
            flow = -flow
            flow[:, :, 0] += np.arange(w)
            flow[:, :, 1] += np.arange(h)[:, np.newaxis]
            halludiff = halluLeft - imgLeft
            halludiff = cv2.remap(halludiff, flow, None, cv2.INTER_LINEAR)
            halluRight = imgRight + halludiff
            halluRight = getFrame(net, halluRight, layers[0])
            np.clip(halluRight, 0, 255, out=halluRight)
            PIL.Image.fromarray(np.uint8(halluRight)).save(os.path.join(outputdir, 'Right', 'frame_000000.png'))

            for v in range(numframe):
                if var_counter < numframe:
                    previousImgLeft = imgLeft
                    previousGrayImgLeft = grayImgLeft

                    newframeLeft = os.path.join(inputdir, 'Left', vids[0][v + 1])
                    print 'Processing: ' + newframeLeft
                    endparam = layers[var_counter % len(layers)]

                    imgLeft = np.float32(PIL.Image.open(newframeLeft))
                    grayImgLeft = cv2.cvtColor(imgLeft, cv2.COLOR_RGB2GRAY)
                    flow = cv2.calcOpticalFlowFarneback(previousGrayImgLeft, grayImgLeft, pyr_scale=0.5, levels=3, winsize=15,
                                                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
                    flow = -flow
                    flow[:, :, 0] += np.arange(w)
                    flow[:, :, 1] += np.arange(h)[:, np.newaxis]
                    halludiffLeft = halluLeft - previousImgLeft
                    halludiffLeft = cv2.remap(halludiffLeft, flow, None, cv2.INTER_LINEAR)
                    halluLeft = imgLeft + halludiffLeft

                    now = time.time()
                    halluLeft = getFrame(net, halluLeft, endparam)
                    later = time.time()
                    difference = int(later - now)
                    saveframe = os.path.joint(outputdir, 'Left', 'frame_%06d.png' % (var_counter))
                    getStats(saveframe, var_counter, numframe, difference)

                    np.clip(halluLeft, 0, 255, out=halluLeft)
                    PIL.Image.fromarray(np.uint8(halluLeft)).save(saveframe)

                    newframeRight = os.path.join(inputdir, 'Right', vids[1][v + 1])
                    print 'Processing: ' + newframeRight
                    endparam = layers[var_counter % len(layers)]

                    imgRight = np.float32(PIL.Image.open(newframeRight))
                    grayImgRight = cv2.cvtColor(imgRight, cv2.COLOR_RGB2GRAY)

                    # Flow from previous frame to current frame
                    flowPrev = cv2.calcOpticalFlowFarneback(previousGrayImgRight, grayImgRight, pyr_scale=0.5, levels=3, winsize=15,
                                                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
                    flowPrev = -flowPrev
                    flowPrev[:, :, 0] += np.arange(w)
                    flowPrev[:, :, 1] += np.arange(h)[:, np.newaxis]
                    halludiffRight = halluRight - previousImgRight
                    halludiffRight = cv2.remap(halludiffRight, flowPrev, None, cv2.INTER_LINEAR)

                    # Flow from left frame to right frame
                    flowLeft = cv2.calcOpticalFlowFarneback(grayImgLeft, grayImgRight, pyr_scale=0.5, levels=3, winsize=15,
                                                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
                    flowLeft = -flowLeft
                    flowLeft[:, :, 0] += np.arange(w)
                    flowLeft[:, :, 1] += np.arange(h)[:, np.newaxis]
                    halludiffLeft = halluLeft - imgLeft
                    halludiffLeft = cv2.remap(halludiffLeft, flowLeft, None, cv2.INTER_LINEAR)

                    halluRight = imgRight + halludiffRight / 2 + halludiffLeft / 2

                    now = time.time()
                    halluRight = getFrame(net, halluRight, endparam)
                    later = time.time()
                    difference = int(later - now)
                    saveframe = os.path.joint(outputdir, 'Right', 'frame_%06d.png' % (var_counter))
                    getStats(saveframe, var_counter, numframe, difference)

                    np.clip(halluRight, 0, 255, out=halluRight)
                    PIL.Image.fromarray(np.uint8(halluRight)).save(saveframe)

                    previousImgRight = imgRight
                    previousGrayImgRight = grayImgRight

                    var_counter += 1
                else:
                    print 'Finished processing all frames'
        else:
            img = np.float32(PIL.Image.open(os.path.join(inputdir, frame0)))
            h, w, c = img.shape
            hallu = getFrame(net, img, layers[0])
            np.clip(hallu, 0, 255, out=hallu)
            PIL.Image.fromarray(np.uint8(hallu)).save(os.path.join(outputdir, 'frame_000000.png'))
            grayImg = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

            for v in range(numframe):
                if var_counter < numframe:
                    previousImg = img
                    previousGrayImg = grayImg

                    newframe = os.path.join(inputdir, vids[v + 1])
                    print 'Processing: ' + newframe
                    endparam = layers[var_counter % len(layers)]

                    img = np.float32(PIL.Image.open(newframe))
                    grayImg = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                    flow = cv2.calcOpticalFlowFarneback(previousGrayImg, grayImg, pyr_scale=0.5, levels=3, winsize=15,
                                                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
                    flow = -flow
                    flow[:, :, 0] += np.arange(w)
                    flow[:, :, 1] += np.arange(h)[:, np.newaxis]
                    halludiff = hallu - previousImg
                    halludiff = cv2.remap(halludiff, flow, None, cv2.INTER_LINEAR)
                    hallu = img + halludiff

                    now = time.time()
                    hallu = getFrame(net, hallu, endparam)
                    later = time.time()
                    difference = int(later - now)
                    saveframe = os.path.joint(outputdir, 'frame_%06d.png' % (var_counter))
                    getStats(saveframe, var_counter, numframe, difference)

                    np.clip(hallu, 0, 255, out=hallu)
                    PIL.Image.fromarray(np.uint8(hallu)).save(saveframe)
                    var_counter += 1
                else:
                    print 'Finished processing all frames'
    else:
        # process anim frames
        for v in range(numframe):
            if var_counter < numframe:
                vid = vids[v]
                h, w = frame.shape[:2]
                s = 0.05  # scale coefficient  

                print 'Processing: ' + os.path.join(inputdir, vid)

                # setup
                now = time.time()
                endparam = layers[var_counter % len(layers)]
                frame = getFrame(net, frame, endparam)
                later = time.time()
                difference = int(later - now)
                saveframe = os.path.join(outputdir, 'frame_%06d.png' % (var_counter))
                getStats(saveframe, var_counter, numframe, difference)

                # save image
                PIL.Image.fromarray(np.uint8(frame)).save(saveframe)

                # setup next image
                newframe = os.path.join(inputdir, vids[v + 1])

                # blend
                if blend == 0:
                    newimg = PIL.Image.open(newframe)
                    if preview is not 0:
                        newimg = resizePicture(newframe, preview)
                    frame = newimg
                else:
                    frame = morphPicture(saveframe, newframe, blend, preview)

                # setup next frame
                frame = np.float32(frame)
                var_counter += 1
            else:
                print 'Finished processing all frames'


def extractVideo(inputdir, outputdir):
    print subprocess.Popen('ffmpeg -i ' + inputdir + ' -f image2 ' + outputdir + '/image-%06d.png', shell=True,
                           stdout=subprocess.PIPE).stdout.read()


def createVideo(inputdir, outputdir, framerate):
    print subprocess.Popen('ffmpeg -r ' + str(
        framerate) + ' -f image2 -i "' + inputdir + '/frame_%6d.png" -c:v libx264 -crf 20 -pix_fmt yuv420p -tune fastdecode -tune zerolatency -profile:v baseline ' + outputdir,
                           shell=True, stdout=subprocess.PIPE).stdout.read()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DeepDreamAnim')
    parser.add_argument('-i', '--input', help='Input directory', required=True)
    parser.add_argument('-o', '--output', help='Output directory', required=True)
    parser.add_argument('-p', '--preview', help='Preview image width. Default: 0', type=int, required=False)
    parser.add_argument('-oct', '--octaves', help='Octaves. Default: 4', type=int, required=False)
    parser.add_argument('-octs', '--octavescale', help='Octave Scale. Default: 1.4', type=float, required=False)
    parser.add_argument('-itr', '--iterations', help='Iterations. Default: 10', type=int, required=False)
    parser.add_argument('-j', '--jitter', help='Jitter. Default: 32', type=int, required=False)
    parser.add_argument('-z', '--zoom', help='Zoom in Amount. Default: 1', type=int, required=False)
    parser.add_argument('-s', '--stepsize', help='Step Size. Default: 1.5', type=float, required=False)
    parser.add_argument('-b', '--blend', help='Blend Amount. Default: 0.5', type=float, required=False)
    parser.add_argument('-l', '--layers', help='Layers Loop. Default: inception_4c/output', nargs="+", type=str,
                        required=False)
    parser.add_argument('-e', '--extract', help='Extract Frames From Video.', type=int, required=False)
    parser.add_argument('-c', '--create', help='Create Video From Frames.', type=int, required=False)
    parser.add_argument('-g', '--guide', help='Guided dream image input.', type=str, required=False)
    parser.add_argument('-flow', '--flow', help='Optical Flow.', type=int, required=False)
    parser.add_argument('-gpu', '--gpu', help='Use GPU or CPU.', type=int, required=False)
    parser.add_argument('-f', '--framerate', help='Video creation Framerate.', type=int, required=False)
    parser.add_argument('-n','--binocular', help='Create 3D dream images from binocular input', type=int,
                        required=False)

    args = parser.parse_args()

    if args.extract is 1:
        extractVideo(args.input, args.output)
    elif args.create is 1:
        framerate = 25
        if args.framerate is not None: framerate = args.framerate
        createVideo(args.input, args.output, framerate)
    else:
        main(args.input, args.output, args.preview, args.octaves, args.octavescale, args.iterations, args.jitter,
             args.zoom, args.stepsize, args.blend, args.layers, args.guide, args.gpu, args.flow, args.binocular)
