from options import Options
import numpy as np
import json
import os
import sys
import subprocess 
import pad
import rulers 
import scipy.misc
import textboxtract
import json2csv
from tqdm import tqdm

def init_folders(base_folder):
	pdf_folder = os.path.join(base_folder, "pdf")
	if not os.path.exists(pdf_folder):
		os.makedirs(pdf_folder)

	json_folder = os.path.join(base_folder, "json")
	if not os.path.exists(json_folder):
		os.makedirs(json_folder)

	png_folder = os.path.join(base_folder, "png")
	if not os.path.exists(png_folder):
		os.makedirs(png_folder)

	outlines_folder = os.path.join(base_folder, "outlines")
	if not os.path.exists(outlines_folder):
		os.makedirs(outlines_folder)

	results_folder = os.path.join(base_folder, "csv_pred")
	if not os.path.exists(results_folder):
		os.makedirs(results_folder)

	return pdf_folder, json_folder, png_folder, outlines_folder, results_folder

def add_outline_url(json_folder, outline_folder):
	for json_file in os.listdir(json_folder):
		json_file_location = os.path.join(json_folder, json_file)
		with open(json_file_location, 'r+') as jfile:
			result = [] # eventually new json file
			tables = json.load(jfile) # current json file
			for table in tables:
				table["outlineURL"] = os.path.join(outline_folder, os.path.basename(table["renderURL"]))
				result.append(table)
			jfile.seek(0)
			jfile.write(json.dumps(result))
			jfile.truncate()

if __name__ == '__main__':
	opt = Options().parse()
	pdf_folder, json_folder, png_folder, outlines_folder, results_folder = init_folders(opt.dataroot)

	if not opt.skip_generate_images:
		print("Generating images")
		os.system('java -jar pdffigures2.jar -e -q -a Table -m ' + png_folder + '/ -d ' + json_folder + '/ ' + pdf_folder + '/')
		for image in tqdm(os.listdir(png_folder)):
			# to do remove from json file
			img = scipy.misc.imread(os.path.join(png_folder, image), mode='RGB').astype(np.float)
			if img.shape[0] > 1024 or img.shape[1] > 1024:
				os.remove(os.path.join(png_folder, image))
				continue
			img = pad.pad(img, (1024, 1024, 3))
			scipy.misc.imsave(os.path.join(png_folder, image), img)

	if not opt.skip_predict:
		print("Predicting outlines")
		if opt.model == 'pix2pixHD':
			subprocess.call(['python', './pix2pixHD/predict.py', '--name', 'gen-tables', '--checkpoints_dir', opt.checkpoint_dir,  '--dataroot', opt.dataroot, '--loadSize', '1024', '--fineSize', '1024', '--no_instance', '--label_nc', '0', '--results_dir', outlines_folder, '--mode', opt.mode, '--which_epoch', opt.epoch])
		elif opt.model == 'encoder-decoder-skip':
			subprocess.call(['python', './segmentation/bulk_predict.py', '--input_folder', png_folder, '--output_folder', outlines_folder, '--checkpoint_path', opt.checkpoint_dir, '--crop_height', '1024', '--crop_width', '1024', '--model', 'Encoder-Decoder-Skip'])
		else:
			print("Unknown model")
			exit(-1)

	# Interpret ruling lines and write individual cells to json file
	if not opt.skip_find_cells:
		print("Finding cells")
		rulers.rule_pdffigures(json_folder, outlines_folder)

	# Extract the text, using the bounding boxes, from the original PDF
	if not opt.skip_extract_text:
		print("Extracting text")
		textboxtract.extract(json_folder, pdf_folder)

	# Create CSV files from the extracted text and locations of said text
	if not opt.skip_create_csv:
		print("Creating csv")
		json2csv.json2csv(json_folder, results_folder)