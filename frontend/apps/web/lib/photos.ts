// Stock photography for the marketing pages, from Pexels (https://www.pexels.com/license/: free to use, no
// attribution required; we keep each photo's page for reference). Served from Pexels' image CDN, which resizes on
// request (`w`, `h`, `fit=crop`). Before launch, consider copying these to our own storage (Bunny) so the site
// doesn't depend on another CDN.

export type Photo = { src: string; alt: string; page: string };

const P = (id: string, file: string, slug: string, alt: string): Photo => ({
  src: `https://images.pexels.com/photos/${id}/${file}`,
  alt,
  page: `https://www.pexels.com/photo/${slug}-${id}/`,
});

export const PHOTOS = {
  hero: P("16504592", "pexels-photo-16504592/free-photo-of-woman-sitting-with-book-at-library.jpeg",
    "woman-sitting-with-book-at-library", "A student reading in a library"),
  reading: P("33904722", "pexels-photo-33904722/free-photo-of-female-student-reading-business-book-in-library.jpeg",
    "female-student-reading-business-book-in-library", "A student reading her notes at a desk"),
  thinking: P("39910357", "pexels-photo-39910357/free-photo-of-engaged-student-in-classroom-setting.jpeg",
    "engaged-student-in-classroom-setting", "A student thinking during a lesson"),
  online: P("4144294", "pexels-photo-4144294.jpeg", "person-in-black-long-sleeve-shirt-sitting-in-front-of-computer",
    "A student taking notes during an online lesson"),
  classroom: P("3231358", "pexels-photo-3231358.jpeg", "photograph-of-girls-in-a-classroom",
    "Students in school uniform in a classroom"),
  teacherBoard: P("8617773", "pexels-photo-8617773.jpeg", "man-pointing-on-a-blackboard",
    "A teacher explaining at a blackboard"),
  graduate: P("34397468", "pexels-photo-34397468/free-photo-of-joyful-graduate-in-black-gown-holding-diplomas-outdoors.jpeg",
    "joyful-graduate-in-black-gown-holding-diplomas-outdoors", "A graduate in Sri Lanka holding flowers and her diploma"),
  phone: P("3768917", "pexels-photo-3768917.jpeg",
    "selective-focus-photo-of-woman-in-blue-denim-jacket-using-her-phone-while-holding-a-book",
    "A student using her phone while holding a book"),
  physics: P("9785602", "pexels-photo-9785602.jpeg", "boy-and-girl-playing-with-newton-s-cradle",
    "Two students with a Newton's cradle"),
  chemistry: P("37951908", "pexels-photo-37951908/free-photo-of-young-scientist-in-laboratory-analyzing-chemical-solution.jpeg",
    "young-scientist-in-laboratory-analyzing-chemical-solution", "A student testing a solution in a chemistry lab"),
  maths: P("5184957", "pexels-photo-5184957.jpeg", "pink-pen-on-white-paper", "Equations written in a notebook"),
  combinedMaths: P("6238030", "pexels-photo-6238030.jpeg", "person-writing-on-white-paper", "A student working through maths problems"),
  biology: P("32213405", "pexels-photo-32213405/free-photo-of-female-scientist-using-microscope-in-laboratory.jpeg",
    "female-scientist-using-microscope-in-laboratory", "A student using a microscope"),
  science: P("8471895", "pexels-photo-8471895.jpeg", "close-up-photo-of-a-smart-girl-looking-at-the-microscope",
    "A young student looking into a microscope"),
  ict: P("4974912", "pexels-photo-4974912.jpeg", "person-coding-on-a-macbook-pro", "Code on a laptop screen"),
  english: P("5676740", "pexels-photo-5676740.jpeg", "laptop-and-books-on-brown-wooden-table", "English grammar books on a desk"),
} satisfies Record<string, Photo>;

/** A Pexels image at a given width (and height, cropped). */
export function pexels(src: string, w: number, h?: number): string {
  return `${src}?auto=compress&cs=tinysrgb&fit=crop&w=${w}${h ? `&h=${h}` : ""}`;
}

/** The photo for a subject (by its slug or name), if we have one. */
export function subjectPhoto(subject: string | null | undefined): Photo | null {
  const key = (subject ?? "").toLowerCase();
  if (key.includes("physics")) return PHOTOS.physics;
  if (key.includes("chemistry")) return PHOTOS.chemistry;
  if (key.includes("combined")) return PHOTOS.combinedMaths;
  if (key.includes("math")) return PHOTOS.maths;
  if (key.includes("biology")) return PHOTOS.biology;
  if (key.includes("science")) return PHOTOS.science;
  if (key.includes("ict") || key.includes("comput")) return PHOTOS.ict;
  if (key.includes("english")) return PHOTOS.english;
  return null;
}
