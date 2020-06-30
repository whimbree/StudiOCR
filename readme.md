# StudiOCR
StudiOCR is an application to index notes and make them searchable by using OCR.

- Select .JPG or .PNG files to create a document
- Search through a document to see if it has any matching text
- Any matching text will be highlighted with a colored box based on confidence level

# Main Window 
![Image of MainWindow](https://github.com/BSpwr/StudiOCR/blob/ui/images/MainWindow.PNG)
- Click the Add New Document button to open the add new document window interface
- Click on a document thumbnail (which is generated from the first page) to open the document window interface
- Toggle remove mode to remove existing documents
![Image of RemoveDocument](https://github.com/BSpwr/StudiOCR/blob/ui/images/RemoveDocument.PNG)
- Search for a document based on document name by typing in the search bar with the DOC bullet selected
- Search for a document based on matching OCR text by typing in the search bar with the OCR bullet selected  

## Add New Document Window
![Image of AddDocument](https://github.com/BSpwr/StudiOCR/blob/ui/images/AddDocument.PNG)
- Add/Remove .JPG or .PNG files to be processed by OCR into a document in the database
- Input the document name
- Click on the info icon to display a window explaining document options 
![Image of Information](https://github.com/BSpwr/StudiOCR/blob/ui/images/Information.PNG)
- Select the processing model you wish to use: Best (for accuracy) or Fast (for speed)
- Select whether you wish to do image preprocessing (convert to grayscale and increase text contrast) 
- PSM Number:

PSM Number | Value
------------ | -------------
3 | Fully automatic page segmentation, but no OSD. (Default)
4 | Assume a single column of text of variable sizes.
5 | Assume a single uniform block of vertically aligned text.
6 | Assume a single uniform block of text.
7 | Treat the image as a single text line.
8 | Treat the image as a single word.
9 | Treat the image as a single word in a circle.
10 | Treat the image as a single character.
11 | Sparse text. Find as much text as possible in no particular order.
12 | Sparse text with OSD.
13 | Raw line. Treat the image as a single text line, bypassing hacks that are Tesseract-specific.

## Document Window
![Image of DocWindow](https://github.com/BSpwr/StudiOCR/blob/ui/images/DocWindow.PNG)
- Enter text in the search bar to search for matching text in the document 
- Click the Next/Previous Page buttons to cycle through the pages in the document
- The current page number is shown at the bottom of the window
- Toggle show matching pages to only display pages with matching text and to cycle through them 
![Image of MatchingPages](https://github.com/BSpwr/StudiOCR/blob/ui/images/MatchingPages.PNG)
- Box Color:

Box Color | Confidence Value
------------ | -------------
Green | Greater than or equal to 80
Blue | Less than 80 and greater than or equal to 40
Red | Less than 40
